print("ATM TRANSACTION")
# atm transaction
class ATM:
    
    def __init__(self, account_number, balance):
        self.account_number = account_number
        self.balance = balance


    def withdraw(self, amount):
        if amount > self.balance:
            print("Insufficient funds")
        else:
            self.balance -= amount
            print(f"Withdrawn: {amount}. New balance: {self.balance}")

    def deposit(self, amount):
        self.balance += amount
        print(f"Deposited: {amount}. New balance: {self.balance}")
    def get_balance(self):
        return self.balance
    def get_account_number(self):
        return self.account_number
    def set_pin(self, pin):
        self.pin = pin
    def generate_receipt(self):
        print(f"Account Number: {self.account_number}, Balance: {self.balance}")

account_number = input("Enter your account number: ")
ac={
    "123456789": 1000,
    "234555": 2000
}
if account_number in ac:
        initial_balance = ac[account_number]
else:
        print("Invalid account number.")
        exit()


#create an instance of the ATM object with the provided account number and initial balance
a1 = ATM(account_number, initial_balance)

print(f"Account Number: {a1.get_account_number()}, Balance: {a1.get_balance()}")
if __name__ == "__main__":
    while True:
        print("\nOptions:")
        print("1. Withdraw")
        print("2. Deposit")
        print("3. Exit")
        print("4. Set PIN")
     
        choice = input("Enter your choice: ")

        if choice == '1':
            amount = float(input("Enter amount to withdraw: "))
            a1.withdraw(amount)
        elif choice == '2':
            amount = float(input("Enter amount to deposit: "))
            a1.deposit(amount)
        elif choice == '3':
            print("Exiting...")
            print("-----------")
            break
        elif choice == '4':
            pin = input("Enter new PIN: ")
            a1.set_pin(pin)
        else:
            print("Invalid choice. Please try again.")
print(f"Final Balance: {a1.get_balance()}")
print("Thank you for using the ATM.")