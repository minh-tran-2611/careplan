import ast
import operator

OPS = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul, ast.Div:operator.truediv}
def calculate(expression: str) -> float:
    if len(expression)>100: raise ValueError("Expression too long")
    def visit(node, depth=0):
        if depth>12: raise ValueError("Expression too deep")
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            if abs(node.value)>1e12: raise ValueError("Number too large")
            return node.value
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):return visit(node.operand,depth+1)*(1 if isinstance(node.op,ast.UAdd) else -1)
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:return OPS[type(node.op)](visit(node.left,depth+1),visit(node.right,depth+1))
        raise ValueError("Only numeric + - * / expressions are allowed")
    return float(visit(ast.parse(expression,mode="eval").body))
