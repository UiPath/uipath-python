# type: ignore

import ast

f = open("dummy-main.py", "r")
source = f.read()


def infer_type(node, env):
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Name):
        return env.get(node.id, "unknown")
    if isinstance(node, ast.BinOp):
        left = infer_type(node.left, env)
        right = infer_type(node.right, env)
        return left if left == right and left != "unknown" else "unknown"
    if isinstance(node, ast.UnaryOp):
        return infer_type(node.operand, env)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return type(node).__name__.lower()
    if isinstance(node, ast.Dict):
        return "dict"
    return "unknown"


class AssignmentCollector(ast.NodeVisitor):
    def __init__(self):
        self.env = {}

    def visit_Assign(self, node):
        t = infer_type(node.value, self.env)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if not isinstance(node.value, ast.Constant):
                    self.env[target.id] = [
                        ast.get_source_segment(source, node.value),
                        t,
                    ]
                else:
                    self.env[target.id] = [node.value.value, t]
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name):
            t = infer_type(node.value, self.env) if node.value else "unknown"
            self.env[node.target.id] = [node.value.value, t]
        self.generic_visit(node)


class AssetManagerCallVisitor(ast.NodeVisitor):
    def __init__(self, env):
        self.env = env
        self.set_mapping = {}
        self.retrieve_mapping = {}

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Attribute):
            return self.generic_visit(node)
        method = node.func.attr
        # Assume calls are made as AssetManager.setAsset(...) or .retrieveAsset(...)
        # node.func.value could be alias, need to have a map for alias imports
        attrId = (
            node.func.value.attr
            if isinstance(node.func.value, ast.Attribute)
            else node.func.value.id
        )
        func = (
            node.func.value
            if isinstance(node.func.value, ast.Name)
            else node.func.value.value
        )
        if isinstance(func, ast.Name) and attrId == "AssetManager":
            if method == "setAsset" and len(node.args) >= 2:
                name_node = node.args[0]
                value_node = node.args[1]
                if not isinstance(name_node, ast.Constant) and not isinstance(
                    name_node, ast.Name
                ):
                    self.set_mapping["expression"] = ast.get_source_segment(
                        source, name_node
                    )
                else:
                    asset_name = (
                        [name_node.value]
                        if isinstance(name_node, ast.Constant)
                        else infer_type(name_node, self.env)
                    )
                    value_type = infer_type(value_node, self.env)
                    self.set_mapping[asset_name[0]] = value_type
            elif method == "retrieveAsset" and len(node.args) >= 1:
                name_node = node.args[0]
                asset_name = (
                    name_node.value
                    if isinstance(name_node, ast.Constant)
                    else infer_type(name_node, self.env)
                )
                default_type = "optional"
                for kw in node.keywords:
                    if kw.arg == "default":
                        default_type = infer_type(kw.value, self.env)
                        break
                self.retrieve_mapping[asset_name] = default_type
        self.generic_visit(node)


if __name__ == "__main__":
    tree = ast.parse(source, filename="dummy-main.py")
    collector = AssignmentCollector()
    collector.visit(tree)
    visitor = AssetManagerCallVisitor(collector.env)
    visitor.visit(tree)

    class ImportVisitor(ast.NodeVisitor):
        def __init__(self):
            self.imports = {}

        def visit_ImportFrom(self, node):
            module = node.module if node.module else ""
            for alias in node.names:
                if module == "sdk" and alias.name == "AssetManager":
                    self.imports[alias.asname] = f"{module}.{alias.name}"
            self.generic_visit(node)

    import_visitor = ImportVisitor()
    import_visitor.visit(tree)

    print("Imports:")
    for imp in import_visitor.imports:
        print(imp)
    print("setAsset mapping:")
    for name, typ in visitor.set_mapping.items():
        print(f"{name} => {typ}")
    # print("\nretrieveAsset mapping:")
    # for name, typ in visitor.retrieve_mapping.items():
    #     print(f"{name}: {typ}")
