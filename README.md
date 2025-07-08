# WebSynthesis

<img src="./figure/WebSynthesis.png" alt="overview" style="zoom:20%; margin: 0 auto; display: block;" />

## World Model-Guided MCTS for Efficient WebUI-Trajectory Synthesis
WebSynthesis is a framework integrating **world model** learning and **Monte Carlo Tree Search** (MCTS), designed to significantly reduce the cost of online synthesis of high-quality Web UI trajectories. Through a two-stage curriculum, including UI fundamental understanding and UI behavior cloning, the policy agent acquires web navigation capabilities.

![framwork](./figure/framework.jpg)

## Two-stage Curriculum Learning
![class](./figure/class.png)


## Data Collection (MCTS)

1. **Clone the GitHub Repository:**
   ```
   git clone https://github.com/LucusFigoGao/WebSynthesis.git
   ```

2. **Collection:**
   ```bash
   cd WebMCTS
   bash run.sh          # run MCTS
   pyhton merge.py      # merge the data
   ```

## Data Resources 
### UI Fundamental Understanding

|   Model Name    |                           Base Model                                            |                           Training Data                                            |                           LoRA                            |
| :-------------: | :-------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------: | :---------------------------------------------------------: |
| TextUI-Cap-7B | [Qwen2.5-Instruct-7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)            | [TextUI-dense-caption-training-data](https://huggingface.co/datasets/yifeigao/WebSynthesis/blob/main/textui-caption2k.json) | [🤗 link](https://huggingface.co/yifeigao/WebSynthesis/tree/main/TextUI-Cap-7B)  |
| TextUI-Func-7B | [Qwen2.5-Instruct-7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | [TextUI-functionality-training-data](https://huggingface.co/datasets/yifeigao/WebSynthesis/blob/main/textui-function6k.json) | [🤗 link](https://huggingface.co/yifeigao/WebSynthesis/tree/main/TextUI-Func-7B)  |
| TextUI-Trans-7B | [Qwen2.5-Instruct-7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)            | [TextUI-state-transition-training-data](https://huggingface.co/datasets/yifeigao/WebSynthesis/blob/main/textui-transmission7k.json) | [🤗 link](https://huggingface.co/yifeigao/WebSynthesis/tree/main/TextUI-Trans-7B)  |

### UI Behavior Cloning
|   Model Name    |                           Base Model                                            |                           Training Data                                            |                           LoRA                            |
| :-------------: | :-------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------: | :---------------------------------------------------------: |
| WebSynthesis-7B | [Qwen2.5-Instruct-7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)            | [WebSynthesis-training-data](https://huggingface.co/datasets/yifeigao/WebSynthesis/tree/main/websynthesis.json) | [🤗 coming soon](https://huggingface.co/yifeigao/WebSynthesis)  |
| OS-Genesis-TextUI-7B | [Qwen2.5-Instruct-7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | [OS-Genesis-training-data](https://huggingface.co/datasets/yifeigao/WebSynthesis/tree/main/os_genesis_sft7k.json) | [🤗 coming soon](https://huggingface.co/yifeigao/WebSynthesis)  |


## Main Experiment
![main-exp](./figure/main-exp.png)

## Ablation Studies
![aba-exp](./figure/ablation.png)

## Scaling Analysis
![scaling-exp](./figure/scaling.png)

## Citation 📖

🫶 If you are interested in our work or find this repository / our data helpful, please consider using the following citation format when referencing our paper:

```bibtex
@misc{gao2025websynthesisworldmodelguidedmctsefficient,
   title={WebSynthesis: World-Model-Guided MCTS for Efficient WebUI-Trajectory Synthesis}, 
   author={Yifei Gao and Junhong Ye and Jiaqi Wang and Jitao Sang},
   year={2025},
   eprint={2507.04370},
   archivePrefix={arXiv},
   primaryClass={cs.AI},
   url={https://arxiv.org/abs/2507.04370}, 
}
```
