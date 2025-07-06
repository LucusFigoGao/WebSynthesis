import re

from models.models import *
from utils.text_utils import *
from utils.obs_opt import *

prefix_string_world = "In summary, the next web page observation is "
prefix_string_policy = "In summary, the next action I will perform is"


def get_proposal(
    prompt: str, 
    policy_model: str, 
    temperature: float = 0.7, 
    max_tokens: int = 4096, 
    seed: int = 170, 
    max_length: int = 8192, 
    truncation: bool = True,
    do_sample: bool = True, 
    max_new_tokens: int = 4096
    ):
    response = []
    cnt = 2
    
    if policy_model == 'deepseek-chat':
        while not response and cnt:
            response = deepseek(prompt, model=policy_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{policy_model}>response fail!\n')
            return []
        else:
            return response
    elif 'qwen' in policy_model:
        while not response and cnt:
            response = qwen(prompt, model=policy_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{policy_model}>response fail!\n')
            return []
        else:
            return response
    elif 'gpt' in policy_model or 'claude' in policy_model:
        while not response and cnt:
            response = gpt(prompt, model=policy_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{policy_model}>response fail!\n')
            return []
        else:
            return response
    elif policy_model == 'Qwen/Qwen2.5-72B-Instruct':
        while not response and cnt:
            response = siliconflow(prompt, model=policy_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{policy_model}>response fail!\n')
            return []
        else:
            return response
    else:
        print('This method of getting responses is not yet supported!\n')
        return []

def get_state(
    prompt: str, 
    world_method: str, 
    temperature: float = 0.7, 
    max_tokens: int = 4096, 
    seed: int = 170, 
    max_length: int = 8192, 
    truncation: bool = True,
    do_sample: bool = True, 
    max_new_tokens: int = 4096
    ):
    response = []
    cnt = 2
    
    if world_method == 'deepseek-chat':
        while not response and cnt:
            response = deepseek(prompt, model=world_method, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{world_method}>response fail!\n')
            return []
        else:
            return response
    
    elif 'gpt' in world_method:
        while not response and cnt:
            response = gpt(prompt, model=world_method, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{world_method}>response fail!\n')
            return []
        else:
            return response
    
    elif 'qwen' in world_method:
        while not response and cnt:
            response = qwen(prompt, model=world_method, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{world_method}>response fail!\n')
            return []
        else:
            return response
    
    elif world_method == 'Qwen/Qwen2.5-72B-Instruct':
        while not response and cnt:
            response = siliconflow(prompt, model=world_method, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{world_method}>response fail!\n')
            return []
        else:
            return response
    
    elif world_method == 'local':
        while not response and cnt:
            response = local_inference_model(
                prompt, max_length=max_length, truncation=truncation, do_sample=do_sample,
                max_new_tokens=max_new_tokens, temperature=temperature
            )
            cnt -= 1
        if not response:
            print(f'obtain<{world_method}>response fail!\n')
            return []
        else:
            return response
    
    else:
        print('This method of getting responses is not yet supported!\n')
        return []

def get_value(
    prompt: str, 
    reward_model: str, 
    temperature: float = 0.7, 
    max_tokens: int = 4096, 
    seed: int = 170, 
    max_length: int = 8192, 
    truncation: bool = True,
    do_sample: bool = True, 
    max_new_tokens: int = 4096
    ):
    response = []
    cnt = 2
    
    if reward_model == 'deepseek-chat':
        while not response and cnt:
            response = deepseek(prompt, model=reward_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{reward_model}>response fail!\n')
            return []
        else:
            return response
    elif 'qwen' in reward_model:
        while not response and cnt:
            response = qwen(prompt, model=reward_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{reward_model}>response fail!\n')
            return []
        else:
            return response
    
    elif 'gpt' in reward_model:
        while not response and cnt:
            response = gpt(prompt, model=reward_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{reward_model}>response fail!\n')
            return []
        else:
            return response
    
    elif reward_model == 'Qwen/Qwen2.5-72B-Instruct':
        while not response and cnt:
            response = siliconflow(prompt, model=reward_model, temperature=temperature, max_tokens=max_tokens)
            cnt -= 1
        if not response:
            print(f'obtain<{reward_model}>response fail!\n')
            return []
        else:
            return response
    else:
        print('This method of getting responses is not yet supported!\n')
        return []

def extract_a11y_prediction(text: str) -> str:
    """
    提取<a11y>标签中的预测内容，兼容标签后可能存在的换行符
    
    Args:
        text: 包含<a11y>标签的原始文本
    
    Returns:
        提取到的预测内容，如果未找到则返回空字符串
    """
    # 正则模式：匹配<a11y>标签，允许标签后紧跟换行符和空白字符
    pattern = r'<a11y>\s*([\s\S]*?)\s*</a11y>'
    match = re.search(pattern, text)
    return match.group(1) if match else None

def washing_response_4_world_model(response: str) -> str:
    
    # 如果模型调用没有返回结果，直接返回空字符串
    if not response:
        print("[ERROR] 模型调用没有返回结果!")
        return ''
    
    # 将```<content>```中的content提取出来
    state = extract_a11y_prediction(response)
    
    if not state:
        print("[ERROR] 世界模型指令跟随能力失败")
        print("="*100)
        print(response)
        print("="*100)
        return ''    
    
    return state

def washing_action_4_policy_model(response: str, state: str) -> str:
    
    # 如果模型调用没有返回结果，直接返回空字符串
    if not response:
        print("[ERROR] 模型调用没有返回结果!")
        return '', ''
    
    thinking, exec_action = parse_action_thinking(raw_action=response)
    if thinking == '' or exec_action == '':
        print("[ERROR] 策略模型指令跟随能力失败")
        print("="*100)
        print(response)
        print("="*100)
        return '', ''
    
    try:
        # 将文本web页面信息(A11y)转化为树结构
        browser_node = parse_text_to_tree(state)
        # 从根节点开始将树上的所有节点设置为不可见
        parse_node_descendants(node=browser_node, action=action_set_invisible)
    except:
        print("[ERROR] 页面结构解析失败")
        return '', ''
    
    try:
        # 提取action_str中确定的节点信息
        target_node_id, action_str = parse_action(exec_action, browser_node)    
    except:
        print(f"[Error] 不合法操作导致无法解析 {exec_action}")
        return '', ''
    
    # 处理scroll, goto, go_back, stop等情况
    if target_node_id is None:
        print(f"None Id-type action {action_str}")
        return response, exec_action
    else:
        # 由行动确定目标节点, target_node_id非空
        node = browser_node.search_node_by_id(target_node_id)
        if node is None:
            print(f"[Error] ID不在当前页面 {action_str}")
            return '', ''
    
    return response, exec_action

def washing_value_4_reward_model(response: str, low=0.0, high=5.0) -> str:
    # 如果模型调用没有返回结果，直接返回空字符串
    if not response:
        print("模型调用没有返回结果!")
        return '', low
    
    # 如果前缀不在response中，说明没有遵循指令，直接返回空字符串
    if "Reason" not in response or "Score" not in response:
        print("前缀不在回复中!")
        return '', low
    else:
        pattern = r"Reason:\s*(.*?)\s*Score:\s*(\d+)"
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            reason_content = match.group(1).strip()
        else:
            print("无理由返回!")
            reason_content = ""
        
        if match:
            score_content = match.group(2).strip()
            try:
                score = float(score_content)
                score = min(max(low, score), high)
            except Exception as e:
                print(f'分数输出有误！错误类型:{e}\n')
                return reason_content, low
        else:
            print("无分数输出!")
            return reason_content, low
    
    return reason_content, score

