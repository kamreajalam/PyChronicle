import math

x = 10
y = 20
sum_value = x + y


def greet(name):
    return f"Hello, {name}"


class Student:
    def __init__(self, name):
        self.name = name

    def introduce(self):
        print(greet(self.name))


for i in range(3):
    print(i)

while x > 0:
    print(x)
    x -= 1

if sum_value > 20:
    print("sum is large")
else:
    print("sum is small")

student = Student("Alice")
student.introduce()
print(math.sqrt(sum_value))