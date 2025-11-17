import time
from liku.liku_client import LikuClient
import uuid

def main():
    client = LikuClient()
    
    # 1. Spawn the agent in a new session
    session_key = f"joke-session-{uuid.uuid4()}"
    agent_command = ["/usr/local/bin/python3", "agents/joke-agent/joke_agent.py", session_key]
    
    try:
        pane_info = client.create_pane(
            session=session_key,
            command=agent_command,
            agent_name="joke-agent"
        )
        print(f"Agent spawned in pane: {pane_info['pane_id']}")
        
        # Give the agent a moment to start up
        time.sleep(2)
        
        # 2. Interact with the agent
        print("\nSending initial message to the agent...")
        client.emit_event("user.message", {"text": "Hello, joke-agent!"}, session_key=session_key)
        
        # 3. Observe the agent's response
        time.sleep(2) # Wait for the agent to process the event and respond
        
        print("\nGetting agent's response...")
        events = client.get_events(event_type="agent.message", limit=10)
        
        for event in events:
            if event.get("session_key") == session_key:
                print(f"  - {event['payload']}")
                
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Clean up the agent's session
        if 'pane_info' in locals():
            print(f"\nKilling pane: {pane_info['pane_id']}")
            client.kill_pane(pane_info['pane_id'])

if __name__ == "__main__":
    main()

