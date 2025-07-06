import os
import sys
sys.path.append('./')

import json
import argparse

from utils.search_utils import save_tree
from webMCTS.task import MCTS_Task

"""
index=811
python3 run.py --policy_method=gpt-4o \
    --reward_method=gpt-4o \
        --world_method=gpt-4o \
            --index=${index}
"""

def main(args, data):

    task = MCTS_Task(
        data=intent, 
        state=state, 
        policy_method=args.policy_method, 
        reward_method=args.reward_method, 
        world_method=args.world_method, 
        policy_temperature=1.0, 
        reward_temperature=0.7, 
        world_temperature=0.7, 
        time_limit=6e5, 
        branch=2,
        roll_branch=0, 
        roll_forward_steps=0, 
        chat_mode='chat', 
        end_gate=4.75, 
        use_reflection='common'
    )
    root, node, finish = task.run()

    tree_dict = save_tree(root)
    data.update({'trace': tree_dict})

    with open(f"./data/{args.index}.json", 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, default=100)
    parser.add_argument('--policy_method', type=str, default='Qwen/Qwen2.5-72B-Instruct')
    parser.add_argument('--reward_method', type=str, default='Qwen/Qwen2.5-72B-Instruct')
    parser.add_argument('--world_method', type=str, default='Qwen/Qwen2.5-72B-Instruct')
    args = parser.parse_args()

    with open(f"./config_files/{args.index}.json", 'r') as file:
        data = json.load(file)
    intent, state, sites = data['intent'], data['state'], data['sites']
    print(f"Task{args.index}: ", intent+"\n\n")
    print(state)
    
    if 'shopping' in sites or 'shopping_admin' in sites:
        if os.path.exists(f"./data/{args.index}.json"):
            print(f"Task{args.index} has been finished!")
        else:
            main(args, data)
    