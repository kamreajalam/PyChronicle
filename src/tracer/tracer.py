import sys

def trace(frame, event, arg):
    print(frame.f_code.co_name)
    return trace

sys.settrace(trace)