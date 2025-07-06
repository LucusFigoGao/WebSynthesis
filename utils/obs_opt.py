import re
import random as rd
from functools import partial

RETAINED_PROPERTIES = ["required", "disabled", "checked", "valuemin", "valuemax", "valuetext", "selected", "page_dialog_message"]
UNWANTED_PROPERTIES = ["focused", "autocomplete", "hasPopup", "expanded", "multiselectable", "orientation", "controls"]
UNINTERACTIVE_ROLES = ["StaticText", "LabelText", "main", "heading", "LayoutTable", "tabpanel", "LayoutTableRow", "LayoutTableCell", "time", "list", "contentinfo", "table", "row", "rowheader", "columnheader", "gridcell", "caption", "DescriptionList", "DescriptionListTerm", "DescriptionListDetail", "RootWebArea", "rowgroup", "alert"]
ROLE_REPLACEMENT_DICT = {
    "StaticText": "text",
    "LabelText": "text",
    # "caption": "text",
    # "generic": "text"
}

# a11y_data: treeNode (UI Tree)
class TreeNode:
    def __init__(self, node_id, role, name, depth, **kwargs):
        self.visible = True
        self.node_id = node_id
        self.role = role
        self.name = name
        self.depth = depth
        self.properties = None
        if "properties" in kwargs.keys():
            self.properties = kwargs["properties"]

        self.children = []
        self.parent = None

    def add_child(self, child):
        child.parent = self
        self.children.append(child)

    def copy(self):
        from copy import deepcopy
        new_self = deepcopy(self)
        new_self.children = []
        new_self.parent = None
        return new_self
    
    def get_visible_node_number(self):
        visible_ids = []

        def dfs(current_node):
            if current_node.visible:
                visible_ids.append(current_node.node_id)
            for child in current_node.children:
                dfs(child)

        dfs(self)

        return len(visible_ids)
    
    def delete_tree(self):
        for child in self.children:
            child.delete_tree()
        self.children.clear()
        self.parent = None

    def has_properties(self):
        return getattr(self, "properties", {})
    
    def visible_children(self):
        return [c for c in self.children if c.visible]
    
    def visible_siblings(self):
        if not self.parent:
            return []
        return [n for n in self.parent.children if n.visible and n.node_id != self.node_id]
    
    def siblings(self):
        if not self.parent:
            return []
        return [n for n in self.parent.children if n.node_id != self.node_id]

    def search_node_by_id(self, target_id):
        if self.node_id == target_id or (self.name and f"[{target_id}]" in self.name):
            return self
        for child in self.children:
            result = child.search_node_by_id(target_id)
            if result:
                return result
        return None
    
    def all_children_invisible(self):
        if not self.children:
            return True
        for child in self.children:
            if child.visible:
                return False
        return True
    
    def has_the_same_properties_as(self, another_node):
        node_a_has_properties = getattr(self, "properties", "")
        node_b_has_properties = getattr(another_node, "properties", "")
        if not node_a_has_properties and not node_b_has_properties:
            return True
        elif (node_a_has_properties and not node_b_has_properties) or (not node_a_has_properties and node_b_has_properties):
            return False
        else:
            return self.properties == another_node.properties
        
    def is_identical_to(self, another_node):
        if another_node.children:
            return False
        return self.role == another_node.role and self.name == another_node.name and self.has_the_same_properties_as(another_node=another_node)
        
    def last_sibling(self, visible_required=False):
        if not self.parent:
            return None
        last_sibling_idx = self.parent.children.index(self) - 1
        if last_sibling_idx < 0:
            return None
        if not visible_required:
            return self.parent.children[last_sibling_idx]
        for sibling in self.parent.children[:self.parent.children.index(self):-1]:
            if sibling.visible:
                return sibling
        return None
        
    def next_sibling(self, visible_required=False):
        if not self.parent:
            return None
        next_sibling_idx = self.parent.children.index(self) + 1
        if next_sibling_idx >= len(self.parent.children):
            return None
        if not visible_required:
            return self.parent.children[next_sibling_idx]
        for sibling in self.parent.children[next_sibling_idx:]:
            if sibling.visible:
                return sibling
        return None
    
    def has_identical_siblings(self):
        if not (self.parent and self.all_children_invisible()):
            return False
        if any(sibling.role == self.role and sibling.name == self.name for sibling in self.parent.children if (sibling.node_id != self.node_id and sibling.all_children_invisible())):
            return True
        return False
    
    def has_identical_surrounding_siblings(self):
        if self.last_sibling(visible_required=False):
            if self.is_identical_to(self.last_sibling(visible_required=False)):
                return True
        if self.last_sibling(visible_required=True):
            if self.is_identical_to(self.last_sibling(visible_required=True)):
                return True
        if self.next_sibling(visible_required=False):
            if self.is_identical_to(self.next_sibling(visible_required=False)):
                return True
        if self.next_sibling(visible_required=True):
            if self.is_identical_to(self.next_sibling(visible_required=True)):
                return True
        return False
        
    def is_differentiable(self, strict=False):
        if self.parent and self.parent.role == "row":
            return True
        if not strict and self.has_identical_siblings():
            return False
        if self.has_identical_surrounding_siblings():
            return False
        return True

import re

def trim_trailing_comments(tree_text: str) -> str:
    """去掉可访问性树末尾的说明性文字"""
    node_line = re.compile(r'^\t*\[\d+\]')      # 匹配  [123]  这样的节点行
    kept = []
    for line in tree_text.splitlines():
        if node_line.match(line):
            kept.append(line)         # 正常节点，收下
        elif kept:                    # 已经开始收节点，突然遇到说明文字
            break                     # 后面都不要了
        # 否则（说明开头就不是节点行）继续寻找首个节点
    return "\n".join(kept)

def parse_text_to_tree(text):
    if '[END]' in text:
        text = text.split('[END]')[0]
    
    text = trim_trailing_comments(text)        # new adding
    lines = text.split('\n')

    root = None
    parent_stack = {}
    old_level = 0

    for line in lines:
        if line.strip() == "":
            continue
        line_strip = line.strip()
        line_parts = line_strip.split(' ')
        id = line_parts[0][1:-1]
        type = line_parts[1]
        text = ' '.join(line_parts[2:])
        level = 0
        for char in line:
            if char == '\t':
                level += 1
            else:
                break
        
        # —— 修补开始  ——
        if root is not None and level == 0:
            level = old_level if old_level != 0 else 1       # 把误判的“第二根”安排在上一节点所在层
        # —— 修补结束  ——
            
        node = TreeNode(id, type, text, level)

        if line.startswith('\t'):
            parent_stack[level].add_child(node)
        else:
            if root is None:
                #! 去除后续潜在的root节点
                root = node

        parent_stack[level+1] = node
        old_level = level

    return root

def remove_unwanted_characters(text):
    text = text.replace('\xa0', ' ')
    cleaned_text = re.sub(r'[^\w\s,.!?;:\-\'\"()&/\u2019@]+', '', text, flags=re.UNICODE)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    return cleaned_text.strip()

def search_node_by_id(node, target_id):
    if node.node_id == target_id:
        return node
    for child in node.children:
        result = search_node_by_id(child, target_id)
        if result:
            return result
    return None

def action_replace_node_role(node:TreeNode, role_replacement_dict:dict):
    if node.role in role_replacement_dict.keys():
        node.role = role_replacement_dict[node.role]

def action_remove_unwanted_characters(node:TreeNode):
    node.name = remove_unwanted_characters(node.name)

def action_remove_unwanted_properties(node:TreeNode):
    if node.has_properties():
        node.properties = {p: node.properties[p] for p in node.properties.keys() if p not in UNWANTED_PROPERTIES}
        if node.parent and node.parent.role=="row" and not node.properties["required"]:
            del node.properties["required"]
        if len(node.properties) == 0:
            node.properties = None

def action_remove_redundant_statictext_node(node:TreeNode):
    if not node.visible:
        return
    if not (node.all_children_invisible() and node.role in ["StaticText", "LabelText", "caption"]):
        return
    if (not node.name) or (node.parent and node.name in node.parent.name) or (node.parent and any(node.name in sibling.name for sibling in node.siblings())):
        node.visible = False

def action_merge_statictext_to_parent(node:TreeNode):
    if not node.visible:
        return
    if not (node.all_children_invisible() and node.role in ["StaticText", "LabelText", "caption"]):
        return
    if node.parent and not node.parent.name and len(node.parent.children) == 1:
        node.parent.name = node.name
        node.visible = False

def action_merge_menuitem_and_option(node:TreeNode):
    if not node.visible:
        return
    if not ((node.visible_children() and all(c.role=="menuitem" for c in node.visible_children())) or (node.visible_children() and all(c.role=="option" for c in node.visible_children()))):
        return
    if node.visible_children()[0].role == "menuitem":
        if not node.name.strip():
            node.name = "; ".join([action_return_visible_node(c).strip()[len("menuitem "):] for c in node.visible_children()])
        else:
            node.name += ": " + "; ".join([action_return_visible_node(c).strip()[len("menuitem "):] for c in node.visible_children()])
    elif node.visible_children()[0].role == "option":
        if not node.name.strip():
            node.name = "; ".join([action_return_visible_node(c).strip()[len("option "):] for c in node.visible_children()])
        else:
            node.name += ": " + "; ".join([action_return_visible_node(c).strip()[len("option "):] for c in node.visible_children()])
    for c in node.visible_children():
        c.visible = False

def action_merge_description_list(node:TreeNode):
    if not node.visible:
        return
    def reformat_sublist(current_list_term_buffer):
        if len(current_list_term_buffer) > 1:
            list_term_node_appended_name = []
            for n in current_list_term_buffer[1:]:
                list_term_node_appended_name.append(n.name)
                n.visible = False
            current_list_term_buffer[0].name += ": " + "; ".join(list_term_node_appended_name)
            
    if not node.role == "DescriptionList":
        return
    for child in node.visible_children():
        if child.role == "DescriptionListDetail" and not child.name and len(child.visible_children()) == 1:
            child.name = action_return_visible_node(child.visible_children()[0]).strip()
            child.visible_children()[0].visible = False
    list_term_buffer = []
    for child in node.visible_children():
        if child.role == "DescriptionListTerm" and child.all_children_invisible():
            reformat_sublist(current_list_term_buffer=list_term_buffer)
            list_term_buffer = [child]
        elif child.role == "DescriptionListDetail" and child.all_children_invisible() and list_term_buffer:
            list_term_buffer.append(child)
        elif child.role == "DescriptionListDetail" and not child.all_children_invisible():
            list_term_buffer = []
        else:
            reformat_sublist(current_list_term_buffer=list_term_buffer)
            list_term_buffer = []
        reformat_sublist(current_list_term_buffer=list_term_buffer)

def action_remove_image(node:TreeNode):
    if not node.visible:
        return
    if node.all_children_invisible() and (node.role=="img" or node.name=="Image"):
        node.visible = False

def action_set_invisible(node:TreeNode):
    node.visible = False

def action_set_visible(node:TreeNode):
    node.visible = True

def action_set_visible_if_with_name(node:TreeNode):
    if node.name:
        node.visible = True

def action_reformat_table(node:TreeNode):
    if not node.visible:
        return
    def merge_gridcell(gridcell_node:TreeNode):
        if gridcell_node.role not in ["gridcell", "columnheader", "rowheader", "LayoutTableCell"] or not gridcell_node.visible:
            return
        gridcell_buffer = []
        parse_node_descendants(gridcell_node, action_return_visible_node, gridcell_buffer)
        if len(gridcell_buffer) == 1:
            return
        gridcell_buffer = [s.strip() for s in gridcell_buffer]
        if gridcell_node.name:
            gridcell_node.name += "\t" + "\t".join(gridcell_buffer[1:])
        else:
            gridcell_node.name = "\t".join(gridcell_buffer[1:])
        parse_node_descendants(gridcell_node, action_set_invisible)
        gridcell_node.visible = True

    try:
        if node.role == "table":

            def reformat_subtable(row_list, current_table_children):
                import copy
                new_table_children = copy.deepcopy(current_table_children)
                if row_list:
                    # if row_list[0].children[0].role == "columnheader":
                    if any(row_0_child.role == "columnheader" for row_0_child in row_list[0].children):
                        if new_table_children and any(n.visible for n in new_table_children):
                            new_table_children.append(TreeNode(node_id=row_list[0].node_id, role="row", name="", depth=row_list[0].depth))
                        for i, row in enumerate(row_list):
                            new_role_name = []
                            for row_element in row.children:
                                new_role_name.append(row_element.name)
                            new_table_children.append(TreeNode(node_id=row.node_id, role="row", name="| "+" | ".join(new_role_name)+" |", depth=row.depth))
                            if i == 0 and len(row_list) > 1:
                                new_table_children.append(TreeNode(node_id=row.node_id, role="row", name="| "+" | ".join(["---"]*len(new_role_name))+" |", depth=row.depth))
                    elif row_list[0].children[0].role == "rowheader":
                        if new_table_children and any(n.visible for n in new_table_children):
                            new_table_children.append(TreeNode(node_id=row_list[0].node_id, role="row", name="", depth=row_list[0].depth))
                        titles = [r.children[0].name for r in row_list]
                        values = [r.children[1].name for r in row_list]
                        new_table_children.append(TreeNode(node_id=row_list[0].node_id, role="row", name="| "+" | ".join(titles)+" |", depth=row_list[0].depth))
                        new_table_children.append(TreeNode(node_id=row_list[0].node_id, role="row", name="| "+" | ".join(["---"]*len(titles))+" |", depth=row_list[0].depth))
                        new_table_children.append(TreeNode(node_id=row_list[0].node_id, role="row", name="| "+" | ".join(values)+" |", depth=row_list[0].depth))
                    elif row_list[0].children[0].role == "gridcell":
                        if new_table_children and any(n.visible for n in new_table_children):
                            new_table_children.append(TreeNode(node_id=row_list[0].node_id, role="row", name="", depth=row_list[0].depth))
                        for row in row_list:
                            new_table_children.append(TreeNode(node_id=row.node_id, role="row", name="| "+" | ".join([row_element.name for row_element in row.children])+" |", depth=row.depth))
                    else:
                        raise NotImplementedError("Unrecognized table format.")
                return new_table_children
            
            new_table_children = []
            row_list = []
            row_mode = False
            for child in node.children:
                if child.role == "row":
                    for row_element in child.visible_children(): # TODO: Visible?
                        merge_gridcell(row_element)

                # if child.role == "row" and child.children[0].role == "columnheader":
                if child.role == "row" and any(row_child.role == "columnheader" for row_child in child.children):
                    row_list = [child]
                    row_mode = False
                elif child.role == "row" and child.children[0].role == "rowheader":
                    if row_mode:
                        row_list.append(child)
                    else:
                        new_table_children = reformat_subtable(row_list=row_list, current_table_children=new_table_children)
                        row_list = [child]
                    row_mode = True
                elif child.role == "row" and child.children[0].role == "gridcell":
                    row_list.append(child)
                    row_mode = False
                elif child.role != "row":
                    new_table_children = reformat_subtable(row_list=row_list, current_table_children=new_table_children)
                    if child.role == "rowgroup":
                        for grandchild in child.visible_children(): # grandchild: row
                            for row_element in grandchild.visible_children(): # TODO: Visible?
                                merge_gridcell(row_element)
                        child.children = reformat_subtable(row_list=child.children, current_table_children=[])
                    new_table_children.append(child)
                    row_list = []
                else:
                    raise NotImplementedError()
            new_table_children = reformat_subtable(row_list=row_list, current_table_children=new_table_children)
            node.children = new_table_children
        elif node.role == "LayoutTable":
            def merge_adjacent_text_nodes(nodes):
                if not nodes:
                    return []

                merged_nodes = []
                current_node = nodes[0]

                for i in range(1, len(nodes)):
                    if current_node.visible and current_node.role in ["LayoutTableCell", "StaticText", "generic"]+list(set(ROLE_REPLACEMENT_DICT.values())) and nodes[i].visible and nodes[i].role in ["LayoutTableCell", "StaticText", "generic"]+list(set(ROLE_REPLACEMENT_DICT.values())):
                        current_node.role = ROLE_REPLACEMENT_DICT["StaticText"]
                        current_node.name += " " + nodes[i].name  # Merge text values
                        nodes[i].visible = False
                    else:
                        merged_nodes.append(current_node)
                        current_node = nodes[i]

                merged_nodes.append(current_node)

                return merged_nodes
            def dfs_merge_text(n:TreeNode):
                if not n.children:
                    return
                for c in n.children:
                    dfs_merge_text(c)
                n.children = merge_adjacent_text_nodes(n.children)
                if len(n.visible_children()) == 1 and n.visible_children()[0].role in ["LayoutTableCell", "StaticText", "generic"]+list(set(ROLE_REPLACEMENT_DICT.values())) and n.role in ["LayoutTableCell", "StaticText", "generic"]+list(set(ROLE_REPLACEMENT_DICT.values())):
                    n.name += "\t" + n.visible_children()[0].name
                    n.visible_children()[0].visible = False
                if n.role == "LayoutTableRow":
                    for row_element in n.children:
                        if row_element.visible and row_element.children:
                            for sub_element in row_element.children:
                                if sub_element.visible:
                                    node_str = action_return_visible_node(sub_element).strip()
                                    row_element.name += f"\t{node_str}"
                            row_element.children = []
                    n.name = "| " + " | ".join([c.name for c in n.children if c.visible]) + " |" # TODO: Visible?
                    for row_element in n.children:
                        row_element.visible = False
            dfs_merge_text(node)
    except Exception as e:
        print("Table reformatting error:", e)

def action_merge_duplicated_headings(node:TreeNode):
    if not node.visible or not node.all_children_invisible() or not node.parent or node.visible_siblings():
        return
    if node.role=="heading" and node.parent.role not in UNINTERACTIVE_ROLES and node.name == node.parent.name:
        node.visible = False
    if node.parent.role=="heading" and node.role not in UNINTERACTIVE_ROLES and node.name == node.parent.name:
        node.parent.node_id = node.node_id
        node.parent.role = node.role
        node.parent.properties = node.properties
        node.parent.children = node.children
        node.visible = False

def action_print_tree(node:TreeNode):
    print("\t" * node.depth + f"{node.visible} {node.depth} [{node.node_id}] {node.role}: {node.name}")

def action_return_visible_node(node:TreeNode, intent_bias=0, mode="concise", **kwargs):
    if not node.visible:
        return None
    if mode == "concise":
        node_str = node.role
        hidden_roles = UNINTERACTIVE_ROLES+list(set(ROLE_REPLACEMENT_DICT.values()))
        if "[" in node.name and "hidden_roles" in kwargs.keys():
            hidden_roles += kwargs["hidden_roles"]
        if node.role not in hidden_roles:
            node_str += f" [{node.node_id}]"    
    elif mode == "verbose":
        node_str = f"{node.role} [{node.node_id}]"
    elif mode == "name_only":
        node_str = node.role
    elif mode == "name_retained_id_only":
        node_str = node.role
        retained_ids = kwargs.get("retained_ids", [])
        if node.node_id in retained_ids:
            node_str += f" [{node.node_id}]"
    
    if node.name:
        node_str += f" {repr(node.name)}"
    if node.has_properties():
        for p in node.properties:
            p_value = node.properties[p]
            node_str += f" [{p}: {p_value}]"
    return "\t" * (node.depth-intent_bias) + node_str

def parse_node_siblings(node:TreeNode, action=action_print_tree, tree_buffer=[]):
    for sibling in node.siblings():
        res_action = action(sibling)
        if res_action:
            tree_buffer.append(res_action)

def parse_node_ancestors(node:TreeNode, action=action_print_tree, tree_buffer=[]):
    res_action = action(node)
    if res_action:
        tree_buffer.append(res_action)
    if node.parent:
        parse_node_ancestors(node=node.parent, action=action, tree_buffer=tree_buffer)

def parse_node_descendants(node:TreeNode, action=action_print_tree, tree_buffer=[]):
    res_action = action(node)
    if res_action:
        tree_buffer.append(res_action)
    for child in node.children:
        parse_node_descendants(node=child, action=action, tree_buffer=tree_buffer)

def prune_tree_fuzzy_node(node:TreeNode): # TODO: Bugs!!!
    if not node.children:
        return
    
    # Iterate over the children in reverse order to safely remove nodes
    fuzzy_children = []
    for child in reversed(node.children):
        prune_tree_fuzzy_node(child)
        if child.all_children_invisible() and not child.is_differentiable(strict=True):
            fuzzy_children.append(child)
    for child in fuzzy_children:
        child.visible = False

def translate_node_to_str(node: TreeNode, mode="concise", **kwargs):
    tree_buffer = []
    parse_node_descendants(node, partial(action_return_visible_node, intent_bias=node.depth, mode=mode, **kwargs), tree_buffer=tree_buffer)
    return "\n".join(tree_buffer[:1000])

def construct_new_DOM_with_visible_nodes(DOM_root:TreeNode):
    def dfs(node:TreeNode):
        if not node.visible:
            return None
        if not node.visible_children():
            return node.copy()
        new_self = node.copy()
        for child in node.visible_children():
            new_child = dfs(child)
            if new_child:
                new_self.add_child(new_child)
        return new_self
    new_DOM_Root = dfs(DOM_root)
    return new_DOM_Root

def prune_tree(root_node, mode="str"):
    root_node_copy = construct_new_DOM_with_visible_nodes(root_node)
    parse_node_descendants(root_node_copy, action_remove_unwanted_characters)
    parse_node_descendants(root_node_copy, action_remove_unwanted_properties)
    parse_node_descendants(root_node_copy, action_remove_redundant_statictext_node)
    parse_node_descendants(root_node_copy, action_remove_image)
    prune_tree_fuzzy_node(root_node_copy)
    parse_node_descendants(root_node_copy, action_remove_image)
    parse_node_descendants(root_node_copy, action_merge_statictext_to_parent)
    parse_node_descendants(root_node_copy, action_remove_redundant_statictext_node)
    parse_node_descendants(root_node_copy, partial(action_replace_node_role, role_replacement_dict=ROLE_REPLACEMENT_DICT))
    parse_node_descendants(root_node_copy, action_merge_menuitem_and_option)
    parse_node_descendants(root_node_copy, action_merge_description_list)
    parse_node_descendants(root_node_copy, action_reformat_table)
    parse_node_descendants(root_node_copy, action_merge_duplicated_headings)

    if mode == "str":
        browser_content = translate_node_to_str(node=root_node_copy, mode="concise")
    elif mode == "node":
        browser_content = construct_new_DOM_with_visible_nodes(root_node_copy)
    return browser_content

def contains_keyword(title, keyword):
    return keyword in title.lower()

MAX_POINT_NUM = 20
MAX_SIBLING_NUM = 10

def parse_action(action_str, DOM_root_node):
    action_str = action_str.strip()
    action = (
        action_str.split("[")[0].strip()
        if "[" in action_str
        else action_str.split()[0].strip()
    )
    
    if 'click' in action:
        match = re.search(r"click ?\[(\d+)\]", action_str)
        if not match:
            raise ValueError(f"Invalid click action {action_str}")
        element_id = match.group(1)
        node = DOM_root_node.search_node_by_id(element_id)
        return element_id, f"click [{element_id}] ({node.role} {node.name})"
    
    elif 'hover' in action:
        match = re.search(r"hover ?\[(\d+)\]", action_str)
        if not match:
            raise ValueError(f"Invalid hover action {action_str}")
        element_id = match.group(1)
        node = DOM_root_node.search_node_by_id(element_id)
        return element_id, f"hover [{element_id}] ({node.role} {node.name})"
    
    elif 'type' in action:
        if not (action_str.endswith("[0]") or action_str.endswith("[1]")):
            action_str += " [1]"

        match = re.search(
            r"type ?\[(\d+)\] ?\[(.+)\] ?\[(\d+)\]", action_str
        )
        if not match:
            raise ValueError(f"Invalid type action {action_str}")
        element_id, text, enter_flag = (
            match.group(1),
            match.group(2),
            match.group(3),
        )
        # enter_flag = True if enter_flag == "1" else False
        # if enter_flag:
        #     text += "\n"
        node = DOM_root_node.search_node_by_id(element_id)
        return element_id, action + f" ({node.name})"
    
    elif 'scroll' in action:
        return None, action_str
    
    elif 'goto' in action:
        return None, action

    elif 'go_back' in action:
        return None, action
    
    elif 'stop' in action:
        return None, action

def get_obs_highlight(action_str, a11y_data, sample_strategy='random'):
    # 将文本web页面信息(A11y)转化为树结构
    root = parse_text_to_tree(a11y_data)
    # 页面状态剪枝，剔除对模型理解有影响的无用文本
    browser_node = prune_tree(root, mode='node')
    # 从根节点开始将树上的所有节点设置为不可见
    parse_node_descendants(node=browser_node, action=action_set_invisible)
    
    try:
        # 提取action_str中确定的节点信息
        target_node_id, action_str = parse_action(action_str, browser_node)
        
        # 处理scroll, goto, go_back, stop等情况
        if target_node_id is None:
            print(f"None Id-type action {action_str}")
            return ''
    except:
        print(f"[Error] InValid action {action_str}")
        return None
        
    # 由行动确定目标节点, target_node_id非空
    node = browser_node.search_node_by_id(target_node_id)
    
    try:
        assert node is not None
        parse_node_ancestors(node=node, action=action_set_visible)                  # 父节点
        num_ancestors = browser_node.get_visible_node_number()
        
        parse_node_descendants(node=node, action=action_set_visible)                # 子节点
        num_descendants = browser_node.get_visible_node_number() - num_ancestors
        
        # sample_node_siblings(node=node, action=action_set_visible_if_with_name)   # 兄弟节点
        
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
            res_action = action_set_visible_if_with_name(sibling)
        
        num_siblings = browser_node.get_visible_node_number() - num_ancestors - num_descendants
        print(f"NODE ID:{node.node_id} | 父节点:{num_ancestors} | 兄弟节点:{num_siblings} | 子节点:{num_descendants}")
    except:
        print(f"[Error] InValid action id [{target_node_id}]")
        return None
    
    # 构建新的summary树（根据当前action对于web page的summary）
    summary_node = construct_new_DOM_with_visible_nodes(browser_node)
    # 再将树结构转化为str表示
    summary_content = translate_node_to_str(node=summary_node)
    parse_node_descendants(node=browser_node, action=action_set_visible)
    return summary_content

