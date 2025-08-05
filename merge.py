import os
import sys
sys.path.append('.')
API_KEY_OPENAI = os.environ.get("API_KEY_OPENAI")
openai_base_url = os.environ.get("openai_base_url")

import json

from utils.query_llm import LLMAPI
from utils.text_utils import read_json_file
from utils.treeNode import build_tree_from_json, TRACE_FORMAT, INPUTS_FORMAT
from utils.prune_mcts import prune_traj_tree, LLM_CACHE
from utils.traj_utils import extract_valuable_trajectories
from webMCTS.prompt import webarena_cot_id_actrees2str_no_na_prompt as policy_agent_prompt
from utils.obs_opt import get_obs_highlight


MAX_RETRY=5
llm = LLMAPI(base_url=openai_base_url, api_key=API_KEY_OPENAI)

def generate_valuable_traj(intent: str, trajectory):
    """
        * 价值轨迹: P--C
        ---------------------------------------------------------------------------
        >>> input:
            OBJECTIVE: intent
            TRAJECTORY: parent_node.trace
            OBSERVATION: parent_node.state
        ---------------------------------------------------------------------------
        >>> output: correct_node.action
    """ 
    res = []
    
    intro, inputs_format = policy_agent_prompt['intro'], policy_agent_prompt['template']
    
    for _, node in enumerate(trajectory):
        
        if node.parent is None:
            continue

        input_str = intro + inputs_format.format(
            objective=intent, 
            previous_action=node.parent.trace,
            observation=node.parent.state,
        )
        
        res.append({
            'input': input_str,
            'output': node.action
        })
    
    return res

def generate_traceable_traj(intent: str, trajectory):
    """
        * 失败的轨迹: A--P--S
        * 成功的轨迹: A--P--C
        * 需要构造的回溯轨迹: A--P--S--P
        >>> 此时只需要合成S--P的"反思"+"回溯行为"即可，A--P--S与失败轨迹完全重合，无需额外处理
        ---------------------------------------------------------------------------
        >>> input:
            OBJECTIVE: intent
            TRAJECTORY: failure_node.trace + <OBSERVATION: failure_node.state, REASON FOR ACTION: reflection, ACTION: go_back>
            OBSERVATION: parent_node.state
        ---------------------------------------------------------------------------
        >>> output: correct_node.action
    """
    
    res = []
    
    # 加载prompt模板
    intro, inputs_format = policy_agent_prompt['intro'], policy_agent_prompt['template']
    
    failure_node, parent_node, correct_node = trajectory
    
    # 合成反思
    reflection_result = llm.llm_gen_reflection(
        objective=intent, 
        fnode_action=failure_node['action'], 
        last_state=parent_node['state'], 
        current_state=failure_node['state']
    )
    print('>>> 完成反思生成:{}'.format(reflection_result))
    
    # 从S-->P的回溯行为
    res.append({
        'input': intro + inputs_format.format(
            objective=intent,
            previous_action=failure_node.trace,
            observation=failure_node.state
        ), 
        'output': reflection_result + " In summary, the next action I will perform is ```go_back```."
    })
    
    # 将回溯行为重新确定为P的历史轨迹
    step_trace = TRACE_FORMAT.format(
        index=failure_node.depth, 
        step_trace=INPUTS_FORMAT.format(
            observation=get_obs_highlight(
                action_str=failure_node.execute_action, 
                a11y_data=failure_node.state, 
                sample_strategy='nearest'
            ),
            reason=reflection_result, 
            action="go_back",
        )
    )

    # 从P-->C的正确行为
    res.append({
        'input': intro + inputs_format.format(
            objective=intent, 
            trajectory=failure_node.trace + step_trace, 
            web_url='', 
            observation=parent_node.state
        ), 
        'output': correct_node.action
    })
    return res

def saving_traceable_traj(intent: str, trajectory):
    saving_dict = dict()
    saving_dict['intent'] = intent
    # failure_node, parent_node, correct_node = trajectory
    type_list = ['failure', 'parent', 'correct']
    
    for node_type, node in zip(type_list, trajectory):
        saving_dict[node_type] = {
            'action': node.action,
            'execute_action': node.execute_action,
            'state': node.state,
            'trace': node.trace,
            'depth': node.depth,
            'numVisits': node.numVisits,
            'V': node.V,
            'v_desc': node.v_desc,
            'isFullyExpanded': node.isFullyExpanded,
            'isTerminal': node.isTerminal,
            'thinking': node.thinking,
            'reflection': node.reflection
        }
    
    return saving_dict
    
def main(file_path):
    file_name = file_path.split('/')[-1]
    data = read_json_file(file_path)
    root = build_tree_from_json(data['trace'])
    print('>>> 完成json格式数据向treeNode轨迹树结构数据转化')
    print('>>> 一共得到{}个节点'.format(root.get_visible_node_number()))
    
    prune_traj_tree(root)
    print('>>> 完成treeNode轨迹树的合并/剪枝')
    print('>>> 一共剩余{}个节点'.format(root.get_visible_node_number()))
    
    print('>>> 将LLM_CACHE保存到fuzzy_match.json')
    json_ready = {f"{k[0]}|||{k[1]}": v for k, v in LLM_CACHE.items()}
    with open("fuzzy_match.json", "w") as f:
        json.dump(json_ready, f, indent=4)
    
    trajectories = extract_valuable_trajectories(root)
    if len(trajectories) == 0:
        print('>>> 合成轨迹失败!')
        return 0
    
    VTraj = [traj_item['trajectory'] for traj_item in trajectories if traj_item['type'] == 'valuable']
    TTraj = [traj_item['trajectory'] for traj_item in trajectories if traj_item['type'] == 'traceable']
    print('>>> 得到{}价值轨迹 ｜ 得到{}回溯轨迹'.format(len(VTraj), len(TTraj)))
    
    valuable_trajectories = []
    for traj in VTraj:
        valuable_traj = generate_valuable_traj(
            intent=data['intent'], 
            trajectory=traj
        )
        valuable_trajectories.extend(valuable_traj)
    print('>>> 完成价值轨迹生成, 一共得到{}条价值轨迹'.format(len(valuable_trajectories)))
    
    if len(valuable_trajectories) > 0:
        saving_dir = os.path.join('./webmcts-vtraj/', file_name)
        with open(saving_dir, 'w') as f:
            json.dump(valuable_trajectories, f, indent=4)
        print('>>> 完成价值轨迹生成并保存到{}'.format(saving_dir))
    
    traceable_trajectories = []
    for traj in TTraj:
        traceable_traj = saving_traceable_traj(
            intent=data['intent'],
            trajectory=traj
        )
        traceable_trajectories.append(traceable_traj)
    print('>>> 完成回溯轨迹生成, 一共得到{}条回溯轨迹'.format(len(traceable_trajectories)))
    
    if len(traceable_trajectories) > 0:
        saving_dir = os.path.join('./webmcts-ttraj/', file_name)
        with open(saving_dir, 'w') as f:
            json.dump(traceable_trajectories, f, indent=4)
        print('>>> 完成回溯轨迹生成并保存到{}'.format(saving_dir))

def check_task_finished(file_name):
    value_traj_dir = './webmcts-vtraj/{}'.format(file_name)
    trace_traj_dir = './webmcts-ttraj/{}'.format(file_name)
    if os.path.exists(value_traj_dir) or os.path.exists(trace_traj_dir):
        return True
    return False

if __name__ == '__main__':
    file_list = os.listdir('./data')
    
    saving_dir_v = './webmcts-vtraj/'
    if not os.path.exists(saving_dir_v):
        os.makedirs(saving_dir_v)
    saving_dir_t = './webmcts-ttraj/'
    if not os.path.exists(saving_dir_t):
        os.makedirs(saving_dir_t)
    
    for index, file_name in enumerate(file_list):
        flag = check_task_finished(file_name)
        if flag:
            print('>>> 任务{}已经完成, 跳过'.format(file_name))
            continue
        
        if not file_name.endswith('.json'):
            continue
        print('>>> 正在处理第{}个文件:{}'.format(index, file_name))
        file_path = os.path.join('./data', file_name)
        main(file_path)
    