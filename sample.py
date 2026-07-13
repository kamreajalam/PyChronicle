x=100
y=200
z=x+y
print(z)
if x==100:
    print("x is 100")
else:
    print("x is not 100")

for i in range(5):
    print(i)

t=2
while t>0:
    print("t is greater than 0")
    t-=1
    print("This is a while loop")

def my_function(a, b):
    return a + b
result = my_function(10, 20)
print(result)

class MyClass:
    def __init__(self, name):
        self.name = name

    def greet(self):
        print(f"Hello, {self.name}!")
my_object = MyClass("Alice")
my_object.greet()