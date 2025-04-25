### client.py
import socket
import threading
import json
from player import Player

HOST = '127.0.0.1'
PORT = 5000

def listen_for_server_messages(sock):
    while True:
        try:
            message = sock.recv(1024).decode()
            if not message:
                break
            data = json.loads(message)
            if data['type'] == 'question':
                print("\nQuestion:", data['question'])
                for idx, option in enumerate(data['options']):
                    print(f"{chr(65+idx)}. {option}")
            elif data['type'] == 'result':
                print("\nCorrect!" if data['correct'] else "\nWrong!")
                print("Your score:", data['score'])
        except Exception as e:
            print(f"Connection lost: {e}")
            break


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        player = Player(s)

        listener = threading.Thread(target=listen_for_server_messages, args=(s,))
        listener.daemon = True
        listener.start()

        while True:
            cmd = input("\nEnter 'q' to get a question or 'a' to answer: ").strip()
            if cmd.lower() == 'q':
                player.request_question()
            elif cmd.lower() == 'a':
                ans = input("Enter your answer (A/B/C/D): ").strip().upper()
                if ans in ['A', 'B', 'C', 'D']:
                    player.send_answer(ans)
                else:
                    print("Invalid answer.")
            else:
                print("Unknown command")


if __name__ == '__main__':
    main()