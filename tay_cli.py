import argparse
import os
import google.generativeai as genai
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.containers import Container
from textual.widget import Widget

class GoalPanel(Widget):
    """A widget to display the agent's name and goal."""
    def __init__(self, name: str, goal: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_name = name
        self.agent_goal = goal

    def compose(self) -> ComposeResult:
        yield Static(f"[b]Agent Name:[/b] {self.agent_name}", classes="goal-text")
        yield Static(f"[b]Goal:[/b] {self.agent_goal}", classes="goal-text")

class TayCliApp(App):
    """A Textual app for the spawned agent CLI."""
    TITLE = "Tay Agent CLI"
    CSS_PATH = "tay_cli.css"
    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self, name: str, goal: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_name = name
        self.agent_goal = goal
        self.chat = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Container(id="goal-container"):
                yield Static("Agent Details", classes="title")
                yield GoalPanel(name=self.agent_name, goal=self.agent_goal)
            yield RichLog(id="log-panel", wrap=True)
            yield Input(placeholder="Enter command...")
        yield Footer()

    def on_mount(self) -> None:
        log_panel = self.query_one(RichLog)
        try:
            # google-auth will automatically find and use the inherited credentials
            genai.configure(transport='rest')
            model = genai.GenerativeModel('gemini-1.5-flash')
            self.chat = model.start_chat(history=[])
            log_panel.write("✅ Gemini 1.5 Flash model initialized successfully.")
            log_panel.write("Gemini-2.5-Flash is now handling the technical elicitation.")

        except Exception as e:
            log_panel.write(f"❌ [bold red]Error initializing Gemini model:[/] {e}")
            log_panel.write("Please ensure you are authenticated with Google Cloud CLI.")

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        """Handle user input submission."""
        log_panel = self.query_one(RichLog)
        user_input = message.value
        message.input.clear()

        if not user_input:
            return

        if not self.chat:
            log_panel.write("[bold red]Chat model is not initialized. Cannot send message.[/]")
            return

        log_panel.write(f"[b]You:[/b] {user_input}")
        log_panel.write(f"[b]{self.agent_name}:[/b] Thinking...")

        try:
            # Stream the response
            response_stream = await self.chat.send_message_async(user_input, stream=True)
            
            # Clear the "Thinking..." message and prepare for the streamed response
            log_panel.clear()
            for old_message in self.chat.history:
                 log_panel.write(f"[b]{'You' if old_message.role == 'user' else self.agent_name}:[/b] {old_message.parts[0].text}")

            log_panel.write(f"[b]{self.agent_name}:[/b] ", end="")
            
            async for chunk in response_stream:
                log_panel.write(chunk.text, end="")

        except Exception as e:
            log_panel.write(f"\n[bold red]An error occurred:[/]\n{e}")

    def action_quit(self) -> None:
        """An action to quit the app."""
        self.exit()

def main():
    parser = argparse.ArgumentParser(description="Tay CLI: A spawned agent environment.")
    parser.add_argument("--name", required=True, help="The name of the agent.")
    parser.add_argument("--goal", required=True, help="The goal for the agent to achieve.")
    args = parser.parse_args()

    app = TayCliApp(name=args.name, goal=args.goal)
    app.run()

if __name__ == "__main__":
    main()


