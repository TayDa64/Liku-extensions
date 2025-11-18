import sys
import time
import random
from database import log_event, init_db


def run_agent(agent_name: str, goal: str) -> None:
    print(f"--- AGENT: {agent_name} ---")
    print(f"Goal: {goal}")
    init_db()
    log_event(agent_name, f"Awakened. Goal: {goal}", "STARTUP")

    while True:
        print(f"[{agent_name}] Thinking...")
        time.sleep(2)
        action = f"Processed partial task for {goal}"
        print(f"Action: {action}")
        log_event(agent_name, action, "ACTION")
        if random.random() > 0.8:
            user_input = input(f"\n[{agent_name}] Need guidance. What next? > ")
            log_event(agent_name, f"User guidance: {user_input}", "INPUT")


def main():
    if len(sys.argv) < 3:
        print("Usage: python agent_runner.py <name> <goal>")
        sys.exit(1)
    run_agent(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
