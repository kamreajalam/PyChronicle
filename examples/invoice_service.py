def calculate_total(price, quantity):
    subtotal = price * quantity
    tax = subtotal * 0.18
    total = subtotal + tax
    return total


def main():
    price = 100
    quantity = 2

    total = calculate_total(price, quantity)

    print("Price:", price)
    print("Quantity:", quantity)
    print("Total:", total)


if __name__ == "__main__":
    main()