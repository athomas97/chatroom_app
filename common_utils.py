import random
from string import ascii_uppercase

def generate_unique_code(rooms, code_length):
    while True:
        code = ""
        for _ in range(code_length):
            code += random.choice(seq=ascii_uppercase)
        if code not in rooms:
            return code
