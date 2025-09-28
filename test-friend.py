import json
import requests
import warnings
import time
import concurrent.futures
from datetime import datetime
from queue import Queue
import os

# 忽略警告信息
warnings.filterwarnings("ignore", message="Unverified HTTPS request is being made.*")

# 用户代理字符串，模仿浏览器
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

# API Key 和 请求URL的模板
if os.getenv("LIJIANGAPI_TOKEN") is None:
    print("本地运行，从环境变量中加载并获取API Key")
    from dotenv import load_dotenv
    load_dotenv()
else:
    print("在服务器上运行，从环境变量中获取API Key")

api_key = os.getenv("LIJIANGAPI_TOKEN")
api_url_template = "https://api.nsmao.net/api/web/query?key={}&url={}"

# 代理链接模板
proxy_url = os.getenv("PROXY_URL")
proxy_url_template = proxy_url + "{}" if proxy_url else None

# 初始化 API 请求队列
api_request_queue = Queue()

# 处理 API 请求
def handle_api_requests():
    while not api_request_queue.empty():
        item = api_request_queue.get()
        headers = {"User-Agent": user_agent}
        link = item['link']
        if not api_key:
            print("API Key 未提供，无法通过API访问")
            item['latency'] = -1
            break
        api_url = api_url_template.format(api_key, link)
        try:
            response = requests.get(api_url, headers=headers, timeout=15, verify=True)
            response_data = response.json()
            if response_data.get('code') == 200:
                latency = round(response_data.get('exec_time', -1), 2)
                print(f"成功通过API访问 {link}, 延迟为 {latency} 秒")
                item['latency'] = latency
            else:
                print(f"API返回错误，code: {response_data.get('code')}，无法访问 {link}")
                item['latency'] = -1
        except requests.RequestException:
            print(f"API请求失败，无法访问 {link}")
            item['latency'] = -1
        time.sleep(0.2)  # 控制速率

# 检查链接可访问性
def check_link_accessibility(item):
    headers = {"User-Agent": user_agent}
    link = item['link']
    latency = -1

    # 直接访问
    try:
        start_time = time.time()
        response = requests.get(link, headers=headers, timeout=15, verify=True)
        latency = round(time.time() - start_time, 2)
        if response.status_code == 200:
            print(f"成功通过直接访问 {link}, 延迟为 {latency} 秒")
            item['latency'] = latency
            return [item, latency]
    except requests.RequestException:
        print(f"直接访问失败 {link}")

    # 代理访问
    if proxy_url_template:
        try:
            proxy_link = proxy_url_template.format(link)
            start_time = time.time()
            response = requests.get(proxy_link, headers=headers, timeout=15, verify=True)
            latency = round(time.time() - start_time, 2)
            if response.status_code == 200:
                print(f"成功通过代理访问 {link}, 延迟为 {latency} 秒")
                item['latency'] = latency
                return [item, latency]
        except requests.RequestException:
            print(f"代理访问失败 {link}")
    else:
        print("未提供代理地址，无法通过代理访问")

    # 如果都失败，加入 API 队列
    item['latency'] = -1
    api_request_queue.put(item)
    return [item, latency]

# 读取 JSON 数据
json_url = 'https://raw.githubusercontent.com/qianmo0021/link/aaea6b8a9bd920cc71e153bad46c620fbe6dd67c/flink_count.json'
response = requests.get(json_url)
if response.status_code == 200:
    data = response.json()
    link_list = data.get('link_list', [])
else:
    print(f"Failed to retrieve data, status code: {response.status_code}")
    exit()

# 并发检查链接
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(check_link_accessibility, link_list))

# 处理 API 队列
handle_api_requests()

# 构造最终结果，包含 avatar
link_status = [
    {
        'name': result[0]['name'],
        'link': result[0]['link'],
        'avatar': result[0].get('avatar', ''),
        'latency': result[0].get('latency', result[1])
    }
    for result in results
]

# 统计数量
accessible_count = sum(1 for result in results if result[1] != -1)
inaccessible_count = sum(1 for result in results if result[1] == -1)
total_count = len(results)

# 当前时间
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 写入结果 JSON
output_json_path = './result.json'
with open(output_json_path, 'w', encoding='utf-8') as file:
    json.dump({
        'timestamp': current_time,
        'accessible_count': accessible_count,
        'inaccessible_count': inaccessible_count,
        'total_count': total_count,
        'link_status': link_status
    }, file, ensure_ascii=False, indent=4)

print(f"检查完成，结果已保存至 '{output_json_path}' 文件。")