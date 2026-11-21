import ast
import operator
import math

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def calculate(expression: str):
    if len(expression) > 200:
        raise ValueError("Expression too long")
    try:
        root = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(root)) > 60:
            raise ValueError("Too complex")

        def visit(n):
            if isinstance(n, ast.Expression):
                return visit(n.body)
            if isinstance(n, ast.Constant) and type(n.value) in (int, float):
                result = n.value
            elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
                result = visit(n.operand) * (1 if isinstance(n.op, ast.UAdd) else -1)
            elif isinstance(n, ast.BinOp) and type(n.op) in OPS:
                a, b = visit(n.left), visit(n.right)
                if isinstance(n.op, ast.Pow) and abs(b) > 10:
                    raise ValueError("Exponent too large")
                result = OPS[type(n.op)](a, b)
            else:
                raise ValueError("Only arithmetic supported")
            if not math.isfinite(result) or abs(result) > 1e15:
                raise ValueError("Result out of range")
            return result

        return visit(root)
    except (SyntaxError, OverflowError, ZeroDivisionError, TypeError) as exc:
        raise ValueError("Invalid arithmetic") from exc
