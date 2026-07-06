import sys

def trace(frame, event, arg):
    print(f"{event}: {frame.f_code.co_name} Line {frame.f_lineno}")
    return trace

def test():
    x = 10
    y = 20
    z = x + y
    return z

sys.settrace(trace)
test()
sys.settrace(None)