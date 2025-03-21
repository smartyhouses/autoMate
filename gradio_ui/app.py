"""
python app.py --windows_host_url localhost:8006 --omniparser_server_url localhost:8000
"""

import json
import os
from pathlib import Path
import argparse
import gradio as gr
from gradio_ui.agent.vision_agent import VisionAgent
from gradio_ui.loop import (
    sampling_loop_sync,
)
import base64
from xbrain.utils.config import Config

from util.download_weights import MODEL_DIR
CONFIG_DIR = Path("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"

INTRO_TEXT = '''
Base on Omniparser to control desktop!
'''

def parse_arguments():

    parser = argparse.ArgumentParser(description="Gradio App")
    parser.add_argument("--windows_host_url", type=str, default='localhost:8006')
    parser.add_argument("--omniparser_server_url", type=str, default="localhost:8000")
    return parser.parse_args()
args = parse_arguments()


def setup_state(state):
    # 如果存在config，则从config中加载数据
    config = Config()
    if config.OPENAI_API_KEY:
        state["api_key"] = config.OPENAI_API_KEY
    else:
        state["api_key"] = ""
    if config.OPENAI_BASE_URL:
        state["base_url"] = config.OPENAI_BASE_URL
    else:
        state["base_url"] = "https://api.openai.com/v1"
    if config.OPENAI_MODEL:
        state["model"] = config.OPENAI_MODEL
    else:
        state["model"] = "gpt-4o"
    
    if "messages" not in state:
        state["messages"] = []
    if "chatbox_messages" not in state:
        state["chatbox_messages"] = []
    if "auth_validated" not in state:
        state["auth_validated"] = False
    if "responses" not in state:
        state["responses"] = {}
    if "tools" not in state:
        state["tools"] = {}
    if "only_n_most_recent_images" not in state:
        state["only_n_most_recent_images"] = 2
    if 'stop' not in state:
        state['stop'] = False

async def main(state):
    """Render loop for Gradio"""
    setup_state(state)
    return "Setup completed"

def load_from_storage(filename: str) -> str | None:
    """Load data from a file in the storage directory."""
    try:
        file_path = CONFIG_DIR / filename
        if file_path.exists():
            data = file_path.read_text().strip()
            if data:
                return data
    except Exception as e:
        print(f"Debug: Error loading {filename}: {e}")
    return None

def save_to_storage(filename: str, data: str) -> None:
    """Save data to a file in the storage directory."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CONFIG_DIR / filename
        file_path.write_text(data)
        # Ensure only user can read/write the file
        file_path.chmod(0o600)
    except Exception as e:
        print(f"Debug: Error saving {filename}: {e}")

def process_input(user_input, state, vision_agent_state):
    # Reset the stop flag
    if state["stop"]:
        state["stop"] = False
    config = Config()
    config.set_openai_config(base_url=state["base_url"], api_key=state["api_key"], model=state["model"])
    state["messages"].append(
        {
            "role": "user",
            "content": user_input
        }
    )
    state["chatbox_messages"].append(
          {
            "role": "user",
            "content": user_input
        }
    )
    yield state['chatbox_messages'] 
    agent = vision_agent_state["agent"]
    for _ in sampling_loop_sync(
        model=state["model"],
        messages=state["messages"],
        vision_agent = agent
    ):
        if state["stop"]:
            return
        state['chatbox_messages'] = []
        for message in state['messages']:
            # convert message["content"] to gradio chatbox format
            if type(message["content"]) is list:
                gradio_chatbox_content = ""
                for content in message["content"]:
                    # convert image_url to gradio image format
                    if content["type"] == "image_url":
                        gradio_chatbox_content += f'<br/><img style="width: 100%;" src="{content["image_url"]["url"]}">'
                    # convert text to gradio text format
                    elif content["type"] == "text":
                        # agent response is json format and must contains reasoning
                        if is_json_format(content["text"]):
                            content_json = json.loads(content["text"])
                            state['chatbox_messages'].append({
                                "role": message["role"],
                                "content": f'<h3>{content_json["reasoning"]}</h3>'
                            })
                            gradio_chatbox_content +=  f'<br/> <details> <summary>Detail</summary> <pre>{json.dumps(content_json, indent=4, ensure_ascii=False)}</pre> </details>'
                        else:
                            gradio_chatbox_content += content["text"]

                state['chatbox_messages'].append({
                    "role": message["role"],
                    "content": gradio_chatbox_content
                })
            else:
                if is_json_format(message["content"]):
                    content_json = json.loads(message["content"])
                    state['chatbox_messages'].append({
                        "role": message["role"],
                        "content": f'<h3>{content_json["reasoning"]}</h3>'
                    })

                state['chatbox_messages'].append({
                    "role": message["role"],
                    "content": message["content"] if not is_json_format(message["content"]) else json.dumps(json.loads(message["content"]), indent=4, ensure_ascii=False)
                })
        yield state['chatbox_messages']
               
def is_json_format(text):
    try:
        json.loads(text)
        return True
    except:
        return False

def stop_app(state):
    state["stop"] = True
    return "App stopped"

def get_header_image_base64():
    try:
        # Get the absolute path to the image relative to this script
        script_dir = Path(__file__).parent
        image_path = script_dir.parent / "imgs" / "header_bar_thin.png"
        
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return f'data:image/png;base64,{encoded_string}'
    except Exception as e:
        print(f"Failed to load header image: {e}")
        return None


def run():
    with gr.Blocks(theme=gr.themes.Default()) as demo:
        gr.HTML("""
            <style>
            .no-padding {
                padding: 0 !important;
            }
            .no-padding > div {
                padding: 0 !important;
            }
            .markdown-text p {
                font-size: 18px;  /* Adjust the font size as needed */
            }
            </style>
        """)
        state = gr.State({})
        
        setup_state(state.value)
        
        header_image = get_header_image_base64()
        if header_image:
            gr.HTML(f'<img src="{header_image}" alt="autoMate Header" width="100%">', elem_classes="no-padding")
            gr.HTML('<h1 style="text-align: center; font-weight: normal;">autoMate</h1>')
        else:
            gr.Markdown("# autoMate")

        if not os.getenv("HIDE_WARNING", False):
            gr.Markdown(INTRO_TEXT, elem_classes="markdown-text")

        with gr.Accordion("Settings", open=True): 
            with gr.Row():
                with gr.Column():
                    model = gr.Textbox(
                        label="Model",
                        value=state.value["model"],
                        placeholder="输入模型名称",
                        interactive=True,
                    )
                with gr.Column():
                    base_url = gr.Textbox(
                        label="Base URL",
                        value=state.value["base_url"],
                        placeholder="输入基础 URL",
                        interactive=True
                    )
                with gr.Column():
                    gr.Slider(
                        label="N most recent screenshots",
                        minimum=0,
                        maximum=10,
                        step=1,
                        value=2,
                        interactive=True
                    )
            with gr.Row():
                api_key = gr.Textbox(
                    label="API Key",
                    type="password",
                    value=state.value["api_key"],
                    placeholder="Paste your API key here",
                    interactive=True,
                )
        with gr.Row():
            with gr.Column(scale=8):
                chat_input = gr.Textbox(show_label=False, placeholder="Type a message to send to Omniparser + X ...", container=False)
            with gr.Column(scale=1, min_width=50):
                submit_button = gr.Button(value="Send", variant="primary")
            with gr.Column(scale=1, min_width=50):
                stop_button = gr.Button(value="Stop", variant="secondary")

        with gr.Row():
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(
                    label="Chatbot History",
                    autoscroll=True,
                    height=580,
                    type="messages")
                
        def update_model(model, state):
            state["model"] = model

        def update_api_key(api_key_value, state):
            state["api_key"] = api_key_value
        
        def update_base_url(base_url, state):
            state["base_url"] = base_url

        def clear_chat(state):
            # Reset message-related state
            state["messages"] = []
            state["chatbox_messages"] = []
            state["responses"] = {}
            state["tools"] = {}
            return state["chatbox_messages"]

        model.change(fn=update_model, inputs=[model, state], outputs=None)
        api_key.change(fn=update_api_key, inputs=[api_key, state], outputs=None)
        chatbot.clear(fn=clear_chat, inputs=[state], outputs=[chatbot])
        vision_agent = VisionAgent(yolo_model_path=os.path.join(MODEL_DIR, "icon_detect", "model.pt"),
                                 caption_model_path=os.path.join(MODEL_DIR, "icon_caption"))
        vision_agent_state = gr.State({"agent": vision_agent})
        submit_button.click(process_input, [chat_input, state, vision_agent_state], chatbot)
        stop_button.click(stop_app, [state], None)
        base_url.change(fn=update_base_url, inputs=[base_url, state], outputs=None)
    demo.launch(server_name="0.0.0.0", server_port=7888)
