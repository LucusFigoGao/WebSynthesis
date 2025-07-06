import os
import re
import json
from dataclasses import dataclass, asdict
from typing import Optional, List, Union, Dict, Tuple

from utils.treeNode import treeNode
from utils.query_llm import LLMAPI

MAX_RETYR = 5


if os.path.exists("fuzzy_match.json"):
    # Load the existing dictionary from the JSON file
    print("Loading LLM_CACHE from fuzzy_match.json...")
    with open("fuzzy_match.json", "r") as f:
        loaded = json.load(f)
    LLM_CACHE = {tuple(k.split("|||")): v for k, v in loaded.items()}
else:
    LLM_CACHE: Dict[Tuple[str, str], bool] = {}   # {(action1, action2): bool}

def _cache_key(a1: str, a2: str) -> Tuple[str, str]:
    """
    构造对称不区分顺序的 key：
        key(action1, action2) == key(action2, action1)
    """
    return tuple(sorted((a1, a2)))

# --------------------------- 对轨迹错误重复/错误的动作进行合并/剪枝 --------------------------- 

def prune_traj_tree(root: treeNode) -> None:
    """
    就地下修改整棵树，使之满足题目定义的去重规则
    """
    
    # ============ 0. 先处理自身 children 中的 **格式非法** 节点 ============
    for child in list(root.children.values()):
        if judge_format(child.execute_action) is None:
            print(f"[警告] 发现非法 action: {child.execute_action}, 正在尝试剪枝...")
            _splice_bad_node(child)
    
    # ============ 1. 递归剪枝子树 ============
    for child in list(root.children.values()):
        prune_traj_tree(child)

    # ============ 2. 合并 action 与父节点相同的子节点 ============
    for child in list(root.children.values()):       # 必须复制为 list 防止迭代中修改
        if is_same_action(child.execute_action, root.execute_action, n=MAX_RETYR):
            _merge_into(target=root, src=child)

    # 上一步可能新增（移动）了一批子节点，因此再次做后序剪枝，以防产生新的冲突
    for child in list(root.children.values()):
        prune_traj_tree(child)

    # ============ 3. 合并兄弟节点中 action 相同的节点 ============
    _merge_sibling_duplicates(root)

# ---------- 工具函数 ----------
def _merge_into(target: treeNode, src: treeNode) -> None:
    """
    把 src 整棵子树并入 target，然后将 src 从其父节点删除
    """
    if target is src:
        return

    # 先把 src 的孩子“搬家”到 target，若 target 已经有同 action 的孩子，递归合并
    for grand_child in list(src.children.values()):
        # 查找 target 当前是否已有 action 相同的孩子
        same_child = None
        for t_child in target.children.values():
            if is_same_action(t_child.execute_action, grand_child.execute_action, n=MAX_RETYR):
                same_child = t_child
                break

        if same_child is None:
            target.add_child(grand_child)
        else:
            _merge_into(same_child, grand_child)  # action 相同 → 继续向下递归合并

    # 从父节点的 children 中移除 src
    if src.parent:
        src.parent.children.pop(id(src), None)

def _merge_sibling_duplicates(node: treeNode) -> None:
    """
    在 node.children 内部，遇到 action 相同的兄弟节点就合并
    策略：保留“第一棵出现的子树”作为目标，其余并入它
    """
    seen: Dict[str, treeNode] = {}  # key 可以是 action，也可以用 hashable wrapper
    for child in list(node.children.values()):
        # 按“语义相等”而非字符串完全相等来判断
        found_key = None
        for act_key in seen:
            if is_same_action(act_key, child.execute_action, n=MAX_RETYR):
                found_key = act_key
                break

        if found_key is None:
            seen[child.execute_action] = child
        else:
            _merge_into(seen[found_key], child)

def is_same_action(action1, action2, n=1):
    
    llm = LLMAPI(base_url=os.environ.get("qwen_base_url"), api_key=os.environ.get("API_KEY_QWEN"))
    
    # 如果是完全一致的action，直接返回True
    print(f"[判断] 处理 ```{action1}``` 和 ```{action2}``` 是否是相同的action...")
    if action1 == action2:
        return True
    
    elif 'stop' in action1 and 'stop' in action2:
        #! 提取stop [answer] 中的answer部分
        try:
            text1 = STOP_RE.match(action1).group('answer').strip()
        except:
            text1 = action1
        
        try:
            text2 = STOP_RE.match(action2).group('answer').strip()
        except:
            text2 = action2
        
        if text1 == text2:
            return True
        
        #! 构造全局查询key
        key = _cache_key(text1, text2)
        if key in LLM_CACHE:                      # ① 命中缓存
            print(f"[命中缓存Stop] ```{text1}``` 和 ```{text2}``` 是不同的action")
            return LLM_CACHE[key]
        
        print(f"[请求Stop] ```{text1}``` 和 ```{text2}``` 是不同的action，正在请求LLM进行判断...")
        result = llm.llm_fuzzy_match(text1, text2, n=n)
        print(f"[响应] {result}")
        print('='*75)
        LLM_CACHE[key] = result
        return LLM_CACHE[key]
    
    elif 'type' in action1 and 'type' in action2:
        #! 提取type [id] [inputs] [0|1] 中的inputs部分
        try:
            text1 = TYPE_RE.match(action1)['content'].strip()
        except:
            text1 = action1
        try:
            text2 = TYPE_RE.match(action2)['content'].strip()
        except:
            text2 = action2
        
        if text1 == text2:
            return True
        
        #! 构造全局查询key
        key = _cache_key(text1, text2)
        if key in LLM_CACHE:                      # ① 命中缓存
            print(f"[命中缓存Type] ```{text1}``` 和 ```{text2}``` 是不同的action")
            return LLM_CACHE[key]
        
        print(f"[请求Type] ```{text1}``` 和 ```{text2}``` 是不同的action，正在请求LLM进行判断...")
        result = llm.llm_fuzzy_match(text1, text2, n=n)
        print(f"[响应] {result}")
        print('='*75)
        LLM_CACHE[key] = result
        return LLM_CACHE[key]
    
    else:
        return False

def _splice_bad_node(bad: treeNode) -> None:
    """
    删除格式非法的 bad 节点：
      ① 把 bad.children 重新挂到 bad.parent
      ② 如果父节点已有“语义相同”的子节点，走 _merge_into
    """
    parent = bad.parent
    if parent is None:          # 根节点非法，简单跳过；如需更复杂策略可自行扩展
        return None
    
    # 先从 parent.children 移除 bad 本体
    parent.children.pop(id(bad), None)
    
    # 逐个把 bad 的孩子挂到 parent
    for gc in list(bad.children.values()):
        target = None
        # 查 parent 是否已存在 action 相同的孩子
        for sib in parent.children.values():
            if is_same_action(sib.execute_action, gc.execute_action, n=MAX_RETYR):
                target = sib
                break

        if target is None:
            parent.add_child(gc)
        else:
            _merge_into(target, gc)   # 若已存在同 action 子树 → 合并

    # 彻底断开 bad
    bad.children.clear()
    bad.parent = None

# --------- 工具函数 format judge ---------
# ----------------- 1. 正则模式 -----------------
TYPE_RE = re.compile(
    r"""
    ^\s*type                              # action
    \s*\[
        (?P<id>[^\]]+?)                   # id
    \]\s*\[
        (?P<content>[^\]]*?)              # content
    \]
    (?:\s*\[
        (?P<enter>[01])                   # optional enter flag
    \])?
    \s*$""",
    re.IGNORECASE | re.VERBOSE,
)
STOP_RE = re.compile(
    r"""
    ^\s*stop                              # action
    \s*\[
        (?P<answer>[^\]]*?)               # answer
    \]
    \s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# ----------------- 2. 结果数据结构 -----------------
@dataclass
class CleanResult:
    raw: str                    # 原始文本
    cleaned: Optional[str]      # 修复后的文本；无法修复则为 None
    status: str                 # ok / fixed / bad_sample
    reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

# ----------------- 3. 单条修复 -----------------
def clean_action(text: str) -> CleanResult:
    """
    输入一条 action 字符串，返回 CleanResult
    """
    original = text.rstrip("\n")

    # ① 直接匹配
    m_type = TYPE_RE.match(original)
    if m_type:
        return _build_type(m_type, original, fixed=False)

    m_stop = STOP_RE.match(original)
    if m_stop:
        return _build_stop(m_stop, original, fixed=False)

    # ② 轻量修复再匹配
    fixed_line = _light_fix(original)
    if fixed_line != original:
        m_type = TYPE_RE.match(fixed_line)
        if m_type:
            return _build_type(m_type, original, fixed=True)
        m_stop = STOP_RE.match(fixed_line)
        if m_stop:
            return _build_stop(m_stop, original, fixed=True)

    # ③ 仍然失败 → bad_sample
    return CleanResult(raw=original,
                       cleaned=None,
                       status="bad_sample",
                       reason="cannot_parse")

# ----------------- 4. 辅助函数 -----------------
def _light_fix(s: str) -> str:
    """
    只做轻量、高可逆的修改：
      * 把 () 换成 []
      * 折叠多余空白
      * 其它复杂情况留给业务端
    """
    s = s.strip()
    s = re.sub(r"\(", "[", s)
    s = re.sub(r"\)", "]", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _build_type(match: re.Match, original: str, fixed: bool) -> CleanResult:
    gd = match.groupdict()
    miss_enter = gd["enter"] is None
    type_content = gd['content'].strip()
    enter = gd["enter"] if gd["enter"] is not None else "1"
    
    if type_content == '':
        return CleanResult(raw=original,
                           cleaned=None,
                           status="bad_sample",
                           reason="type_content_empty")

    cleaned = f"type [{gd['id'].strip()}] [{type_content}] [{enter}]"
    status = "fixed" if (fixed or miss_enter) else "ok"
    return CleanResult(raw=original, cleaned=cleaned, status=status)

def _build_stop(match: re.Match, original: str, fixed: bool) -> CleanResult:
    answer = match.group('answer').strip()
    answer = 'N/A' if answer == '' else answer
    cleaned = f"stop [{answer}]"
    status = "fixed" if fixed else "ok"
    return CleanResult(raw=original, cleaned=cleaned, status=status)

# ----------------- 5. 批量接口 -----------------
def clean_batch(entries: Union[List[str], List[List[str]], List[tuple]]) -> List[Dict]:
    """
    entries 可以是：
      • ["text_a", "text_b", ...]           （单条模式）
      • [(text_a, text_b), ...] 或 [[a, b], ...] （成对模式）
    返回 List[dict]，方便写 JSONL / Parquet
    """
    output = []
    for idx, item in enumerate(entries):
        if isinstance(item, (list, tuple)):
            # 成对 / 多元素
            res = [clean_action(x).to_dict() for x in item]
            output.append({"idx": idx, "results": res})
        else:
            # 单元素
            output.append({"idx": idx, "result": clean_action(item).to_dict()})
    return output

def judge_format(text):
    if 'type' in text or 'stop' in text:
        result = clean_batch([text])[0]
        return result['result']['cleaned']
    else:
        return text
