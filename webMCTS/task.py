import re
import os
import random as rd

from webMCTS.mcts import MCTS
from models.get_response import *
from utils.search_utils import *
from utils.query_llm import *
from utils.prune_mcts import *


if os.path.exists("./fuzzy_match.json"):
    # Load the existing dictionary from the JSON file
    print("Loading LLM_CACHE from fuzzy_match file...")
    with open("./fuzzy_match.json", "r") as f:
        loaded = json.load(f)
    LLM_CACHE = {tuple(k.split("|||")): v for k, v in loaded.items()}
else:
    LLM_CACHE: Dict[Tuple[str, str], bool] = {}   # {(action1, action2): bool}

class SearchTask(object):
    def __init__(self, data, policy_method, reward_method, world_method) -> None:
        """
            :: data: str, represent the question or task or instruction
            :: policy_method: str, default: ['gpt', 'deepseek', 'qwen2.5']
            :: reward_method: str, default: ['gpt', 'deepseek', 'qwen2.5']
            :: world_method: str, default: ['gpt', 'deepseek', 'qwen2.5']
            :: value_cache: dict{str: float}, ['action': value]
        """
        super().__init__()
        self.question = data
        self.policy_method = policy_method
        self.reward_method = reward_method
        self.world_method = world_method
        self.value_cache = {}
    
    def clear_cache(self):
        self.value_cache = {}
    
    @staticmethod
    def get_next_action_prompt_wrap(intent: str, trace: str, state: str, mode: str = "chat") -> str:
        
        from webMCTS.prompt import webarena_cot_id_actrees2str_no_na_prompt as prompt_template
        
        intro = prompt_template["intro"]               # prompt intro
        examples = prompt_template["examples"]         # few examples
        inputs = prompt_template["template"]           # input template
        
        current = inputs.format(
            objective=intent,                               # instruction
            observation=state,                              # current web state
            previous_action=trace,                          # action trace
        )

        if mode == "chat":
            """
                [
                    {"role": "system", "content": intro}, 
                    {"role": "system", "name": "example_user", "content": example_input}, 
                    {"role": "system", "name": "example_assistant", "content": example_output}, 
                    {"role": "user", "content": current}
                ]
                >>> {"role": "system", "content": output}
            """
            message = [{"role": "system", "content": intro}]
            for (x, y) in examples:
                message.append(
                    {
                        "role": "system",
                        "name": "example_user",
                        "content": x,
                    }
                )
                message.append(
                    {
                        "role": "system",
                        "name": "example_assistant",
                        "content": y,
                    }
                )
            message.append({"role": "user", "content": current})
        
        elif mode == "completion":
            message = f"{intro}\n\n"
            message += "Here are a few examples:\n"
            for example in examples:
                message += f"Observation\n:{example[0]}\n\n"
                message += f"Action: {example[1]}\n\n"
            message += "Now make prediction given the observation\n\n"
            message += f"Observation\n:{current}\n\n"
            message += "Action:"
        
        return message

    @staticmethod
    def get_next_state_predict_prompt_wrap(state: str, action: str, mode: str = "chat") -> str:
        
        from webMCTS.prompt import world_model_next_state_prediction_prompt as prompt_template
        
        intro = prompt_template["intro"]               # prompt intro
        inputs = prompt_template["template"]           # input template
        
        current = inputs.format(
            observation=f"```{state}```",                   # current web state
            action=f"{action}",                             # action trace
        )
        
        if mode == "chat":
            message = [
                {"role": "system", "content": intro}, 
                {"role": "user", "content": current}
            ]
        elif mode == "completion":
            message = f"{intro}\n\n"
            message += f"The current web page observation: ```{state}```\n\n"
            message += f"The previous action: {action}"
        return message
    
    @staticmethod
    def get_step_value_prompt_wrap(intent: str, trace: str, state: str, mode: str = "chat") -> str:
        
        from webMCTS.prompt import osgensis_reward_prompt as prompt_template

        intro = prompt_template["intro"]               # prompt intro
        inputs = prompt_template["template"]           # input template
        
        current = inputs.format(
            intent=intent,                                  # instruction
            trace=trace,                                    # action trace
            state=state,                                    # current web state
        )

        if mode == "chat":
            message = [
                {"role": "system", "content": intro}, 
                {"role": "user", "content": current}
            ]
        elif mode == "completion":
            message = f"{intro}\n\n"
            message += f"** High-level Instruction **:{intent}\n"
            message += f"** Action History **:\n"
            message += f"- Reasoning and Action for Each Step:\n{trace}\n"
            message += f"The current web page's accessibility tree of the last state:\n{state}\n\n"
            message += f"** Your Response **:"
        return message


class MCTS_Task(SearchTask):
    def __init__(
        self, 
        data: str,                                  # str, represent the question or task or instruction
        state: str,                                 # str, represent the initial state of web page
        policy_method,                              # str, default: ['gpt', 'deepseek-chat', 'qwen2.5']
        reward_method,                              # str, default: ['gpt', 'deepseek-chat', 'qwen2.5']
        world_method,                               # str, default: ['gpt', 'deepseek-chat', 'qwen2.5']
        policy_temperature=0.7,                     # float, temperature for policy method
        reward_temperature=0.7,                     # float, temperature for reward method
        world_temperature=0.7,                      # float, temperature for world method
        branch=3,                                   # int, the number of sampling times in extension stage
        roll_policy='greedy',                       # str, rollout policy
        roll_branch=1,                              # int, the number of sampling times in rollout stage
        roll_forward_steps=3,                       # int, the number of rollout steps
        time_limit=None,                            # int, time searching limit
        iteration_limit=None,                       # int, iteration searching limit
        reward_model_type='vm',                     # str, reward model type (outcome reward)
        use_reflection='common',                    # str, reflection type (common, simple)
        end_gate=0.9,                               # int, threshold of task finished reward
        exploration_constant=0.7,                   # float, MCTS UCB epsilon
        inf=1.0,                                    # float, MCTS UCB avoid stackflow
        low=0,                                      # float
        alpha=0.5,                                  # float, MCTS node value weights
        chat_mode='chat', 
        max_tokens = 4096, 
        seed = 42, 
        max_length = 16384, 
        truncation = True, 
        do_sample = True, 
        max_new_tokens = 4096, 
        
        ) -> None:
        super().__init__(data, policy_method, reward_method, world_method)
        
        self.mode = chat_mode
        self.max_tokens = max_tokens
        self.seed = seed
        self.max_length = max_length
        self.truncation = truncation
        self.do_sample = do_sample
        self.max_new_tokens = max_new_tokens
        
        self.init_state = state
        self.branch = branch
        self.roll_policy = roll_policy
        self.roll_branch = roll_branch
        self.roll_forward_steps = roll_forward_steps

        self.time_limit = time_limit
        self.iteration_limit = iteration_limit
        
        self.end_gate = end_gate
        self.use_reflection = use_reflection
        self.reward_model_type = reward_model_type
        
        self.policy_temperature = policy_temperature
        self.reward_temperature = reward_temperature
        self.world_temperature = world_temperature
        
        self.low = low
        self.INF = inf
        self.alpha = alpha
        self.exploration_constant = exploration_constant
        self.current_model_index = 0        # 用于polciy 模型的轮转索引
        
    def clear_cache(self):
        self.value_cache = {}
        self.node_count = 1
    
    def set_limit_type(self):
        if self.time_limit is not None:
            if self.iteration_limit is not None:
                raise ValueError("Cannot have both a time limit and an iteration limit")
            # time taken for each MCTS search in milliseconds
            self.limit_type = 'time'
        else:
            if self.iteration_limit is None:
                raise ValueError("Must have either a time limit or an iteration limit")
            # number of iterations of the search
            if self.iteration_limit < 1:
                raise ValueError("Iteration limit must be greater than one")
            self.limit_type = 'iterations'
    
    def get_next_action(self, trace, state, step):
        """
            output:
                >>> child.action = Policy_model(node.trace, node.state)
            input: 
                :: node.trace: action history till current node
                :: node.state: current state of web page
        """
        prompt = self.get_next_action_prompt_wrap(self.question, trace, state, mode=self.mode)
        
        # 策略模型轮转
        policy_model_list = ['gpt-4o', 'gpt-4.1-mini', 'gpt-4.1']
        policy_method = policy_model_list[self.current_model_index]
        self.current_model_index = (self.current_model_index + 1) % len(policy_model_list)

        response = get_proposal(
            prompt, policy_method, 
            temperature=self.policy_temperature, 
            max_tokens=self.max_tokens, 
            seed=self.seed, max_length=self.max_length, 
            truncation=self.truncation, do_sample=self.do_sample, 
            max_new_tokens=self.max_new_tokens
        )            
        response, action = washing_action_4_policy_model(response, state)        
        print(f"第<{step}>轮 {policy_method} 采取的行动是: {response}\n")
        return response, action
    
    def get_next_state_predict(self, state, action):
        """
            output:
                >>> child.state = World_model(node.state, child.action)
            input: 
                :: node.state: current state of web page
                :: child.action: current action from node to child
        """
        # 如果获取状态过程遇到了stop, 那么直接返回当前状态即可
        if 'stop' in action:
            return state
        
        prompt = self.get_next_state_predict_prompt_wrap(state, action, mode=self.mode)
        response = get_state(
            prompt, self.world_method, 
            temperature=self.world_temperature, 
            max_tokens=self.max_tokens, 
            seed=self.seed, max_length=self.max_length, 
            truncation=self.truncation, do_sample=self.do_sample, 
            max_new_tokens=self.max_new_tokens
        )
        response = washing_response_4_world_model(response)
        print(f"下一帧网页预测为: {response}\n")
        return response
    
    def get_step_value(self, trace, state):
        """
            output:
                >>> child.state = Reward_model(child.trace, child.state)
            input: 
                :: child.trace: action history till child
                :: child.state: next state of web page
        """
        prompt = self.get_step_value_prompt_wrap(self.question, trace, state, mode=self.mode)
        response = get_value(
            prompt, reward_model=self.reward_method, 
            temperature=self.reward_temperature, 
            max_tokens=self.max_tokens, 
            seed=self.seed, max_length=self.max_length, 
            truncation=self.truncation, do_sample=self.do_sample, 
            max_new_tokens=self.max_new_tokens
        )
        reason, value = washing_value_4_reward_model(response, low=self.low, high=5)
        print(f"当前行动的得分: {reason}")
        print(f"当前行动的得分为: {value}\n")
        return value, reason
    
    def get_reflection(self, trace):
        # 如果模拟过程遇到了stop, 那么退出模拟过程直接返回max_V
        stop_pattern = r"stop \[(.*?)\]"
        match = re.search(stop_pattern, trace)
        if match:
            extracted_content = match.group(1)
            return extracted_content
        else:
            return None
    
    def get_simple_reflection(self, trace):
        pass
    
    def duplicate_checker(self, action, action_list):
        # 检查action是否在action_list中
        if action in action_list:
            return True
        else:
            for query_action in action_list:
                if is_same_action(action, query_action):
                    return True
            return False
    
    def run(self):
        self.clear_cache()
        self.set_limit_type()
        root, node, finish = MCTS(self)     # input mcts_task
        
        print('>>> 将LLM_CACHE保存到fuzzy_match.json')
        json_ready = {f"{k[0]}|||{k[1]}": v for k, v in LLM_CACHE.items()}
        with open("./fuzzy_match.json", "w") as f:
            json.dump(json_ready, f, indent=4)
        
        return root, node, finish