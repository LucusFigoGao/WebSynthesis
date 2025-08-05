import json
import time
from openai import OpenAI

MAX_RETRY = 3

fuzzy_match_template = {
   'intro': """### 角色
你是一名精通中文的语义匹配专家，擅长判断任意两段文本在含义上的相似度以及差异原因。
### 任务
1. 输入包含两段文本：
   - 文本 A: 
   - 文本 B: 
2. 判断二者在**语义层面**是否属于“同一意思”或“相似”。  
   - 忽略轻微的措辞差异、同义替换、字面顺序调换。
   - 忽略数据的拼写错误、格式错误、标点符号差异。
   - 关注核心事实、观点或意图是否一致。
3. 产出以下结构化 JSON（仅输出 JSON，不要额外解释）：
```json
{
  "similarity_binary": "<yes|no>",      // yes 表示语义一致或相似
  "similarity_score":  "<0.00-1.00>",   // 0 完全不同，1 完全等价，可保留两位小数
  "analysis": "<一句话解释主要理由>"
}
""", 
   'inputs': """- 文本 A: {TEXT_A}\n- 文本 B: {TEXT_B}""", 
   'output': {
        "similarity_binary": "<yes|no>", 
        "similarity_score":  "<0.00-1.00>", 
        "analysis":          "<一句话解释主要理由>"
    }
}

reflection_cot_prompt = {
    'intro': """You are an autonomous intelligent agent tasked with navigating a web browser. You will be given web-based tasks. These tasks will be accomplished through the use of specific actions you can issue.

Here's the information you'll have:
* The user's objective: This is the task you're trying to complete.
* The current observation of web page. This is a simplified representation of the webpage, refer to as accessibility tree (a11y), providing key information.
* The previous trajectory: This is the `observations`, `thoughts` and `actions` you have just performed. It may be helpful to track your progress. Each step is splited by <step></step> tag.

## Action Space
### URL Navigation Actions:
`go_back`: Navigate to the previously viewed page. 

### Homepage:
If you want to visit other websites. Here is a list of websites you can visit.
`Gitlab`: http://gitlab.com
`OpenStreetMap`: https://www.openstreetmap.org
`OpenStopMarket`: http://onestopmarket.com
`Admin`: http://luma.com/admin
`Redit`: http://reddit.com

## Action Rules:
To be successful, it is very important to follow the following rules:
1. You should think step by step and then issue the next action. Start with a "Let's think step-by-step." phrase.
2. You should only issue an action that is valid given the current web page.
3. You should only issue one action at a time.
4. Generate the action in the correct format. Start with a "In summary, the next action I will perform is" phrase, followed by action inside ``````. For example, "In summary, the next action I will perform is ```click [1234]```".
5. Issue stop action when you think you have achieved the objective. Don't generate anything after stop.""", 

    "template": """OBJECTIVE:
{objective}

Previously, the action:
```
{fnode_action}
```
has been attempted, and this action will not lead to the task completion. Please provide an action for going back to the last observation following the aforementioned format. Give your reason why this action cannot help to complete the task.

Last Observation:
{last_state}

Current Observation:
{current_state}

What's the next action?"""
}

examples = [
    {
        'query': fuzzy_match_template['inputs'].format(
            TEXT_A="Carnegie Mellon University", 
            TEXT_B="Carnegie Mellon University, NYC", 
        ), 
        'output': json.dumps(
            {
                "similarity_binary": "yes", 
                "similarity_score":  "0.95",
                "analysis": "TEXT_A 和 TEXT_B 是同一意思，因为它们都描述了 Carnegie Mellon University 这个机构，TEXT_B额外包含了一个位置信息 NYC"
            }, 
            ensure_ascii=False
        )
    }, 
    {
        'query': fuzzy_match_template['inputs'].format(
            TEXT_A="x-lab", 
            TEXT_B="groups/x-lab", 
        ), 
        'output': json.dumps(
            {
                "similarity_binary": "yes", 
                "similarity_score":  "0.75",
                "analysis": "两段文本结构一致，但 TEXT_B 中将路径 \"x-lab\" 改为 \"groups/x-lab\"，引入了不同命名空间，结构更加完备。"
            }, 
            ensure_ascii=False
        )
    }, 
    {
        'query': fuzzy_match_template['inputs'].format(
            TEXT_A="Public",
            TEXT_B="crew",
        ),
        'output': json.dumps(
            {
                "similarity_binary": "no",
                "similarity_score":  "0.0",
                "analysis": " TEXT_A 中输入了Public，而TEXT_B 中输入了crew，两者代表了完全不同的语义。"
            },
            ensure_ascii=False
        )
    }, 
    {
        'query': fuzzy_match_template['inputs'].format(
            TEXT_A="Product-A: $20, Product-B: $18",
            TEXT_B="A: $20, B: $18",
        ),
        'output': json.dumps(
            {
                "similarity_binary": "yes",
                "similarity_score":  "0.65",
                "analysis": " 尽管TEXT_B的描述相对更简单，但是他们表示相同的含义，都是对商品价格的返回。"
            },
            ensure_ascii=False
        )
    }
]

class LLMAPI:    
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.client = self.create_client()
    
    def create_client(self):
        return OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )
    
    def generate(self, messages: list, model: str, temperature=0.7, max_tokens=8192):
        return self.client.chat.completions.create(
            messages=messages,
            model=model,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _call_llm(self, prompt, n=1):
        outputs = []
        while n > 0:
            n -= 1
            try:
                res = self.generate(
                    messages=[
                        {'role':'system', 'content': 'You are a helpful assistant.'},
                        {'role':'user', 'content': prompt}
                    ],
                    model='qwen-max-2025-01-25',
                    temperature=0.7,
                    max_tokens=256
                )
                outputs.extend([choice.message.content for choice in res.choices])
            except Exception as e:
                print(f"[Error] Error occurred when getting LLM reply!\nError type:{e}\n")
        
        result = outputs[0]
        return result
    
    def llm_fuzzy_match(self, pred, reference, n=1):
        messages=[
            {
                "role": "system",
                "content": f"""{fuzzy_match_template['intro']}\n示例：
    Q：{examples[0]['query']}\nA：{examples[0]['output']}
    Q：{examples[1]['query']}\nA：{examples[1]['output']}
    Q：{examples[2]['query']}\nA：{examples[2]['output']}
    Q：{examples[3]['query']}\nA：{examples[3]['output']}"""
            },
            {
                "role": "user",
                "content": fuzzy_match_template['inputs'].format(
                    TEXT_A=pred,
                    TEXT_B=reference,
                )
            }
        ]

        try_times = 0
        while try_times < MAX_RETRY:
            try:
                completion = self.client.chat.completions.create(
                    model="qwen-max-2025-01-25",
                    messages=messages, 
                    response_format={"type": "json_object"},
                )
                json_string = completion.choices[0].message.content
                parse_reuslt = json.loads(json_string)
                judge, judge_score = parse_reuslt['similarity_binary'], parse_reuslt['similarity_score']
                if judge == "yes" and float(judge_score) >= 0.5:
                    return True
                else:
                    return False
            
            except Exception as e:
                try_times += 1
                print('>>> 第{}次解析结果失败:{}'.format(try_times, e))
                if try_times == MAX_RETRY:
                    return False
    
    def llm_gen_reflection(self, objective, fnode_action, last_state, current_state):
        message = reflection_cot_prompt['intro'] + reflection_cot_prompt['template'].format(
            objective=objective, 
            fnode_action=fnode_action, 
            last_state=last_state, 
            current_state=current_state, 
        )
        
        attempt = 0
        while attempt < MAX_RETRY:
            try:
                completion = self.client.chat.completions.create(
                    model='gpt-4',
                    messages=[{'role': 'user', 'content': message}],
                    temperature=0.7, 
                    max_tokens=16384
                )
                return completion.choices[0].message.content
            except Exception as e:
                error_str = str(e)
                print(f"Attempt {attempt + 1} failed with error: {e}")
                
                # 检查是否是输入长度超限错误
                if "Range of input length should be [1, 30720]" in error_str:
                    print(f"输入长度超过模型限制(30720)，跳过重试")
                    # 直接返回错误信息，不再重试
                    return f"ERROR: 输入长度超过模型限制(30720)"
                
                if attempt + 1 < MAX_RETRY:
                    time.sleep(1)
                else:
                    print(f"Failed to process message after {MAX_RETRY} attempts. Error: {e}")
                    return ''