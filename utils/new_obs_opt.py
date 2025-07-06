import re
import random

from utils.obs_opt import *
from typing import Optional, Dict, List, Tuple


MAX_NODE_NUMS = 10

# 你给出的两类角色
UNINTERACTIVE_ROLES = {
    "StaticText", "LabelText", "main", "heading", "LayoutTable",
    "tabpanel", "LayoutTableRow", "LayoutTableCell", "time", "list",
    "contentinfo", "table", "row", "rowheader", "columnheader", "gridcell",
    "caption", "DescriptionList", "DescriptionListTerm",
    "DescriptionListDetail", "RootWebArea", "rowgroup", "alert"
}
INTERACTIVE_ROLES = {
    'img', 'link', 'button', 'spinbutton', 'searchbox', 'checkbox', 'combobox',
    'menu', 'menubar', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'textbox'
}


TAG_PATTERN = re.compile(
    r"<think>\s*(?P<think>.*?)\s*</think>.*?"
    r"<memory>\s*(?P<memory>.*?)\s*</memory>.*?"
    r"<action>\s*(?P<action>.*?)\s*</action>",
    flags=re.S  # 让 '.' 匹配换行
)

def parse_tags(text: str):
    """
    提取 <think></think>、<memory></memory>、<action></action> 中的内容。

    Parameters
    =======
    text : str
        含有三个标签的完整字符串

    Returns
    -------
    dict | None
        {"think": "...", "memory": "...", "action": "..."}
        若未匹配到三段内容则返回 None
    """
    match = TAG_PATTERN.search(text)
    if not match:
        return None
    return {
        "think":  match.group("think").strip(),
        "memory": match.group("memory").strip(),
        "action": match.group("action").strip(),
    }

import re
from typing import Dict, Optional

# ======= 正则模板 =======
_PATTERNS = {
    # click('a51') | click("123") | click(18282)
    "click": re.compile(r"""^click\(\s*(?:'(?P<id1>[^']+)'|"(?P<id2>[^"]+)"|(?P<id3>\d+))\s*\)$"""),
    # fill('237', 'foo') | fill(45, "bar")
    "fill" : re.compile(
        r"""^fill\(\s*
            (?:'(?P<fid1>[^']+)'|"(?P<fid2>[^"]+)"|(?P<fid3>\d+))\s*,\s*
            (?:'(?P<val1>[^']*)'|"(?P<val2>[^"]*)")\s*\)$""",
        re.X
    ),
    # hover('b8') | hover(18282)
    "hover": re.compile(r"""^hover\(\s*(?:'(?P<hid1>[^']+)'|"(?P<hid2>[^"]+)"|(?P<hid3>\d+))\s*\)$"""),
    # scroll(0, 200) | scroll(-50.2, -100.5)
    "scroll": re.compile(r"""^scroll\(\s*([+-]?\d*\.?\d+)\s*,\s*([+-]?\d*\.?\d+)\s*\)$"""),
    # goto('http://...') | goto("http://...")
    "goto": re.compile(r"""^goto\(\s*(?:'([^']+)'|"([^"]+)")\s*\)$"""),
    # go_back()
    "go_back": re.compile(r"""^go_back\(\s*\)$"""),
    # send_msg_to_user('text ...')  双/单引号皆可
    "send": re.compile(
        r"""^send_msg_to_user\(\s*
            (?:'(?P<msg1>(?:[^'\\]|\\.)*)'|"(?P<msg2>(?:[^"\\]|\\.)*)")\s*\)$""",
        re.X | re.S
    ),
}

# ======= 转换主函数 =======
def convert_action(old_cmd):
    old_cmd = old_cmd.strip()
    # 1) click
    m = _PATTERNS["click"].match(old_cmd)
    if m:
        bid = m.group("id1") or m.group("id2") or m.group("id3")    
        try:
            bid = int(bid)
        except ValueError:
            return None
        return {"input": old_cmd, "output": f"click [{bid}]"}

    # 2) fill → type
    m = _PATTERNS["fill"].match(old_cmd)
    if m:
        bid = m.group("fid1") or m.group("fid2") or m.group("fid3")
        try:
            bid = int(bid)
        except ValueError:
            return None
        val = m.group("val1") or m.group("val2") or ""
        press = 0 if "\n" in val else 1
        return {"input": old_cmd, "output": f"type [{bid}] [{val}] [{press}]"}

    # 3) hover
    m = _PATTERNS["hover"].match(old_cmd)
    if m:
        bid = m.group("hid1") or m.group("hid2") or m.group("hid3")
        try:
            bid = int(bid)
        except ValueError:
            return None
        return {"input": old_cmd, "output": f"hover [{bid}]"}

    # 4) scroll
    m = _PATTERNS["scroll"].match(old_cmd)
    if m:
        dy = float(m.group(2))
        direction = "down" if dy > 0 else "up"
        return {"input": old_cmd, "output": f"scroll [{direction}]"}

    # 5) goto
    m = _PATTERNS["goto"].match(old_cmd)
    if m:
        url = m.group(1) or m.group(2)
        return {"input": old_cmd, "output": f"goto [{url}]"}

    # 6) go_back
    if _PATTERNS["go_back"].match(old_cmd):
        return {"input": old_cmd, "output": "go_back"}

    # 7) send_msg_to_user → stop
    m = _PATTERNS["send"].match(old_cmd)
    if m:
        msg = m.group("msg1") or m.group("msg2") or ""
        return {"input": old_cmd, "output": f"stop [{msg}]"}

    # 其他未匹配
    return None


# ====================== 正则辅助 ======================
ID_LINE_RE = re.compile(
    r"""^\[(?P<bid>[^\]]+)]\s+            # [123]
        (?P<type>\S+)                     # link / button …
        \s*
        (?P<text>.*)                      # 剩余文本
    """,
    re.X,
)

def _parse_line_content(content: str):
    """
    解析行主体 => (bid, type, text)
    - 标准行: [69] link 'abc'
    - Root 行: RootWebArea 'xxx'
    - StaticText … 兜底
    """
    m = ID_LINE_RE.match(content)
    if m:
        return m.group("bid"), m.group("type"), m.group("text")

    parts = content.split(None, 2)        # 最多拆 3 段
    if len(parts) == 1:
        return parts[0], "", ""
    elif len(parts) == 2:
        return parts[0], parts[1], ""
    else:
        return parts[0], parts[1], parts[2]


# ====================== 主函数 ======================
def parse_text_to_tree(raw_text: str) -> Optional[TreeNode]:
    """
    把可访问性树文本解析为 TreeNode 拓扑。
    - 仅首行(无缩进)视为根；之后再次出现 level==0 的行 → 自动调到 level=1
    - 支持 TAB / 4 空格 混合缩进
    - 路径栈算法保证不会 KeyError
    """
    # ---- 去掉 [END] 及尾部日志 ----
    if "[END]" in raw_text:
        raw_text = raw_text.split("[END]")[0]

    lines = raw_text.splitlines()
    root: Optional[TreeNode] = None
    stack: List[TreeNode] = []          # 从 root → 当前节点

    for raw in lines:
        if not raw.strip():
            continue                                 # 跳过空行

        # 1) 统一把 4 空格当作 1 个 TAB 计
        line = raw.replace("    ", "\t")
        level = len(line) - len(line.lstrip("\t"))
        content = line.lstrip("\t").rstrip()

        # 2) 解析内容
        bid, tp, txt = _parse_line_content(content)
        node = TreeNode(node_id=bid, role=tp, name=txt, depth=level)

        # =======- 根节点判断 & 路径维护 =======-
        if root is None:
            # 第一行必为真正 root
            root = node
            stack = [root]
            continue

        # 若非首行且 level==0 ⇒ 视为根的直接子节点
        if level == 0:
            level = 1

        # 回溯 stack 至父层
        while len(stack) > level:
            stack.pop()

        # 若缺层（例如 level 跳跃）→ 用当前可用最高层
        if level > len(stack):
            level = len(stack)

        parent = stack[level - 1]
        parent.add_child(node)

        # 更新 stack
        if len(stack) == level:
            stack.append(node)
        else:
            stack[level] = node

    return root


DIGITS_ONLY = re.compile(r"^\d+$")    # 判断 bid 是否纯数字

def _render_line(node) -> str:
    """
    根据节点属性生成单行字符串（不含缩进）。
    """
    if DIGITS_ONLY.match(node.node_id):               # 典型行: [73] checkbox 'Main Menu'
        parts = [f"[{node.node_id}]", node.role]
    else:                                         # RootWebArea / StaticText 等
        parts = [node.node_id]
        if node.role:
            parts.append(node.role)

    if node.name:
        parts.append(node.name)

    return " ".join(parts).rstrip()

def tree_to_text(root) -> str:
    """
    把 TreeNode 树转换回可读的可访问性树文本。

    Parameters
    =======
    root : TreeNode
        parse_text_to_tree 返回的根节点

    Returns
    -------
    str
        多行字符串，每行以 \\t 表示缩进
    """
    lines: List[str] = []

    def dfs(node: "TreeNode"):
        indent = "\t" * node.depth
        lines.append(indent + _render_line(node))
        for child in node.children:
            dfs(child)

    dfs(root)
    return "\n".join(lines)


# ============ 工具 ============
def iter_tree(root):
    """深度优先，一次性拉平整棵树"""
    stack, nodes = [root], []
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))  # 保持原顺序
    return nodes

def classify_nodes(nodes):
    """返回 (interactive_candidates, uninteractive_candidates)"""
    inter, uninter = [], []
    for n in nodes:
        if n.visible:                   # 原本可见的节点不采，继续保留
            continue
        if not n.is_differentiable(strict=False):
            continue                    # 去除难区分的“重复”节点
        if n.role in INTERACTIVE_ROLES:
            inter.append(n)
        elif n.role in UNINTERACTIVE_ROLES:
            uninter.append(n)
        # 其它角色（未知或 container）忽略；如需包含可加入二者之一
    return inter, uninter

def open_path_to_root(node: "TreeNode"):
    """把 node 到 root 的所有祖先设为可见，确保路径连通"""
    while node:
        node.visible = True
        node = node.parent

def prune_invisible_subtrees(node: "TreeNode"):
    """自顶向下剪掉 invisible 的子树，使返回的子树更紧凑"""
    node.children[:] = [c for c in node.children if c.visible]
    for c in node.children:
        prune_invisible_subtrees(c)

# ============ 主采样函数 ============
def sample_subtree(
    root: "TreeNode",
    N: int,
    ratio_interactive: float = 0.65,
    seed: int = None
    ):
    """
    参数
    ----
    root  : TreeNode        原始可访问性树根
    N     : int             目标采样节点数量
    ratio_interactive :     交互节点占比（例如 0.65）
    seed  : int | None      随机种子，便于复现

    返回
    ----
    TreeNode                已在原树上完成 visible 打标，可再调用 prune_invisible_subtrees(root)
    """
    rng = random.Random(seed)

    # 1) 收集候选
    inter_cands, uninter_cands = classify_nodes(iter_tree(root))
    # print(len(inter_cands), len(uninter_cands))

    # 2) 计算目标配额
    n_inter = round(N * ratio_interactive)
    n_uninter = N - n_inter

    # 3) 考虑候选不足时自动回填
    n_inter = min(n_inter, len(inter_cands))
    n_uninter = min(n_uninter, len(uninter_cands))
    deficit = N - (n_inter + n_uninter)

    # 用剩余较多的一侧回填缺口
    if deficit > 0:
        if len(inter_cands) - n_inter >= len(uninter_cands) - n_uninter:
            n_inter += min(deficit, len(inter_cands) - n_inter)
        else:
            n_uninter += min(deficit, len(uninter_cands) - n_uninter)

    # 4) 随机采样各自配额
    picked_inter   = rng.sample(inter_cands,   n_inter)   if n_inter   else []
    picked_uninter = rng.sample(uninter_cands, n_uninter) if n_uninter else []
    picked_nodes = picked_inter + picked_uninter
    # print(len(picked_inter), len(picked_uninter))

    # 5) 打开可视路径
    for node in picked_nodes:
        open_path_to_root(node)

    # 6) 可选：裁剪不可见子树，生成紧凑返回
    prune_invisible_subtrees(root)
    return root


def state_summary(item: dict, sample_strategy: str = 'random'):
    state, action_str = item['state'], item['output']
    
    #! Step1: root <- parse_text_to_tree(raw_text: A11y_data = state)
    root = parse_text_to_tree(state)
    # 这里将全部的节点设置为不可见很重要，后续采样对应于打开可见节点
    parse_node_descendants(node=root, action=action_set_invisible)
    
    #! Step2.1: 根据输出行动保留对应区域的可访问性树，保证模型训练时输入输出的一致性
    # 如果着一部分不能满足，那么即可以删除这一部分数据
    try:
        target_node_id, new_action_str = parse_action(action_str, root)
    except:
        print(f"[ERROR]: 目标节点对应的行动```{action_str}```解析失败! 原因: 节点ID不存在")
        return None
    
    # 对action落在[scroll, goto, go_back, stop]的特殊情况(无target_node_id)，跳过2.1的剩余步骤
    if target_node_id:
        node = root.search_node_by_id(target_node_id)
        try:
            node.visible = True
            parse_node_ancestors(node=node, action=action_set_visible)                  # 父节点
            num_ancestors = root.get_visible_node_number()
            
            parse_node_descendants(node=node, action=action_set_visible)                # 子节点
            num_descendants = root.get_visible_node_number() - num_ancestors
            
            """
                如果父节点+子节点数量大于MAX_POINT_NUM，则采样min(MAX_SIBLING_NUM, len(sibling_nodes))个兄弟节点
                    e.x., 父+子=25，那么至多采样min(10, len(sibling_nodes))
                如果父节点+子节点数量小于MAX_POINT_NUM：则采样min(max(MAX_POINT_NUM - 父节点 - 子节点, MAX_SIBLING_NUM), len(sibling_nodes))个兄弟节点
                    e.x., 父+子=15，那么至多采样min(max(5, 10), len(sibling_nodes))
            """
            sibling_nodes = node.siblings()    
            if (num_descendants + num_ancestors) >= MAX_POINT_NUM:
                sample_num = min(MAX_SIBLING_NUM, len(sibling_nodes))
            else:
                sample_num = min(max(MAX_POINT_NUM - num_descendants - num_ancestors, MAX_SIBLING_NUM), len(sibling_nodes))
            
            if sample_strategy == 'random':
                # 随机采样sample_num个兄弟节点
                sampled_sibling_nodes = rd.sample(sibling_nodes, sample_num)
            elif sample_strategy == 'nearest':
                # 根据近邻关系选择sample_num个兄弟节点
                elements_with_dist = [(sibling, abs(int(node.node_id)-int(sibling.node_id))) for sibling in sibling_nodes]
                elements_with_dist.sort(key=lambda x: x[1])
                sampled_sibling_nodes = [elem for elem, _ in elements_with_dist[:sample_num]]
            
            for sibling in sampled_sibling_nodes:
                action_set_visible_if_with_name(sibling)
            
            num_siblings = root.get_visible_node_number() - num_ancestors - num_descendants
            # print(f"NODE ID:{node.node_id} | 父节点:{num_ancestors} | 兄弟节点:{num_siblings} | 子节点:{num_descendants}")
            
        except:
            print(f"[ERROR]: 目标节点[{target_node_id}]的父节点、兄弟节点、子节点提取失败")
            return None
    
    #! Step2.2: 将一棵部分可见的树进行余下部分的采样
    try:
        root = sample_subtree(root, N=MAX_NODE_NUMS, seed=42)
    except:
        print('[ERROR] 采样剩余部分过程中出现错误，仅返回目标区域的摘要数据！')
        return tree_to_text(root)
    
    #! Step3: summary_contents <- tree_to_text(root: TreeNode = root)
    return tree_to_text(root)