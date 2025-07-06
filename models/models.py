import os

API_KEY_DEEPSEEK = os.environ.get("API_KEY_DEEPSEEK")
API_KEY_QWEN = os.environ.get("API_KEY_QWEN")
API_KEY_OPENAI = os.environ.get("API_KEY_OPENAI")
deepseek_base_url = os.environ.get("deepseek_base_url")
qwen_base_url = os.environ.get("qwen_base_url")
openai_base_url = os.environ.get("openai_base_url")
webSimulator_port = os.environ.get("webSimulator_port", 8000)

from openai import OpenAI
from threading import Lock  # 新增：导入线程锁

completion_tokens = prompt_tokens = 0
tokens_lock = Lock()  # 新增：创建令牌计数器锁

deepseek_client = OpenAI(api_key=API_KEY_DEEPSEEK, base_url=deepseek_base_url)
qwen_client = OpenAI(api_key=API_KEY_QWEN, base_url=qwen_base_url)
gpt_client = OpenAI(api_key=API_KEY_OPENAI, base_url=openai_base_url)
webSimulator_client = OpenAI(api_key="", base_url=f"http://localhost:{webSimulator_port}/v1")


def deepseek(messages, model='deepseek-chat', temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    out = []
    cnt = 5
    while cnt:
        try:
            out = deepseek_call(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)[0]
            break
        except Exception as e:
            print(f"Error occurred when getting deepseek reply!\nError type:{e}\n")
            cnt -= 1
    deepseek_usage(backend=model)
    return out

def qwen(messages, model='qwen-plus', temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    out = []
    cnt = 5
    while cnt:
        try:
            out = qwen_call(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)[0]
            break
        except Exception as e:
            print(f"Error occurred when getting qwen reply!\nError type:{e}\n")
            cnt -= 1
    qwen_usage(backend=model)
    return out

def gpt(messages, model='gpt-4o', temperature=0.7, max_tokens=2048, n=1, stop=None) -> list:
    out = []
    cnt = 5
    while cnt:
        try:
            out = gpt_call(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)[0]
            break
        except Exception as e:
            print(f"Error occurred when getting openai reply!\nError type:{e}\n")
            cnt -= 1
    gpt_usage(backend=model)
    return out

def deepseek_call(messages, model='deepseek-chat', temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    global completion_tokens, prompt_tokens
    outputs = []
    while n > 0:
        cnt = min(n, 20)
        n -= cnt
        res = deepseek_client.chat.completions.create(
            model=model,
            messages=messages, 
            stream=False, 
            temperature=temperature, 
            max_tokens=max_tokens
        )
        outputs.extend([choice.message.content for choice in res.choices])
        # 修改：使用锁保护全局变量更新
        with tokens_lock:
            completion_tokens += res.usage.completion_tokens
            prompt_tokens += res.usage.prompt_tokens
    return outputs

def qwen_call(messages, model='qwen-plus', temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    global completion_tokens, prompt_tokens
    outputs = []
    while n > 0:
        cnt = min(n, 20)
        n -= cnt
        res = qwen_client.chat.completions.create(
            model=model,
            messages=messages, 
            stream=False, 
            temperature=temperature, 
            max_tokens=max_tokens
        )
        outputs.extend([choice.message.content for choice in res.choices])
        # 修改：使用锁保护全局变量更新
        with tokens_lock:
            completion_tokens += res.usage.completion_tokens
            prompt_tokens += res.usage.prompt_tokens
    return outputs

def gpt_call(messages, model='gpt-4o', temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    global completion_tokens, prompt_tokens
    outputs = []
    while n > 0:
        cnt = min(n, 20)
        n -= cnt
        res = gpt_client.chat.completions.create(
            model=model,
            messages=messages, 
            stream=False, 
            temperature=temperature, 
            max_tokens=max_tokens
        )
        outputs.extend([choice.message.content for choice in res.choices])
        # 修改：使用锁保护全局变量更新
        with tokens_lock:
            completion_tokens += res.usage.completion_tokens
            prompt_tokens += res.usage.prompt_tokens
    return outputs

def webSimulator(messages, model='qwen2_5_world-model', temperature=0.7, max_tokens=2048, n=1, stop=None) -> list:
    out = []
    cnt = 5
    while cnt:
        try:
            out = webSimulator_call(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)[0]
            break
        except Exception as e:
            print(f"Error occurred when getting webSimulator reply!\nError type:{e}\n")
            cnt -= 1
    return out

def webSimulator_call(messages, model='qwen2_5_world-model', temperature=0.7, max_tokens=2048, n=1, stop=None) -> list:
    outputs = []
    while n > 0:
        cnt = min(n, 20)
        n -= cnt
        res = webSimulator_client.chat.completions.create(
            model=model,
            messages=messages, 
            stream=False, 
            temperature=temperature, 
            max_tokens=max_tokens
        )
        outputs.extend([choice.message.content for choice in res.choices])
    return outputs

def deepseek_usage(backend='deepseek-chat'):
    global completion_tokens, prompt_tokens
    if backend == "deepseek-chat":
        cost = completion_tokens / 1000000 * 0.1 + prompt_tokens / 1000000 * 2
    else:
        cost = -1
    print({"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost})
    return {"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost}

def qwen_usage(backend='qwen-plus'):
    global completion_tokens, prompt_tokens
    if backend == "qwen-plus":
        cost = completion_tokens / 1000000 * 0.8 + prompt_tokens / 1000000 * 2
    else:
        cost = -1
    print({"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost})
    return {"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost}

def gpt_usage(backend='gpt-4o'):
    global completion_tokens, prompt_tokens
    if backend == "gpt-4o":
        cost = 1 * 1.25 * (prompt_tokens + completion_tokens * 4) / 500000
    elif backend == 'gpt-4.1':
        cost = 1 * 1 * (prompt_tokens + completion_tokens * 4) / 500000
    elif backend == 'gpt-4.1-mini':
        cost = 1 * 0.02 * (prompt_tokens + completion_tokens * 4) / 500000
    elif backend == 'gpt-4.5-preview':
        cost = 1 * 37.5 * (prompt_tokens + completion_tokens * 2) / 500000
    elif backend == 'gpt-4':
        cost = 1 * 15 * (prompt_tokens + completion_tokens * 2) / 500000
    elif backend == 'claude-sonnet-4-20250514':
        cost = 1 * 1.5 * (prompt_tokens + completion_tokens * 5) / 500000
    elif backend == 'claude-opus-4-20250514':
        cost = 1 * 7.5 * (prompt_tokens + completion_tokens * 5) / 500000
    else:
        cost = -1
    print({"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost})
    return {"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost}
