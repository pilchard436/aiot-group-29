import gradio as gr
import whisper

whisper_model = whisper.load_model("tiny.en")

def process_input(audio):
    result = whisper_model.transcribe("audio")["result"]
    transcription = f"Placeholder for audio: {whisper_model.transcribe(audio)}"
    llm_response = f"Placeholder for LLM response"
    smartwatch_response = f"Placeholder for smartwatch response"
    return transcription, llm_response, smartwatch_response

ui = gr.Interface(
    inputs=[
        gr.Audio(sources=["microphone"], type="filepath", label="Voice Input"),
    ],
    fn=process_input,
    outputs=[
        gr.Textbox(label="Transcription/Input"),
        gr.Textbox(label="LLM Response"),
        gr.Textbox(label="Smartwatch Response")
    ],
    title="Voice Assistant",
    description="My capabilities: XXX",
    # allow_flagging="never"
    )

if __name__ == "__main__":
    ui.launch(debug=False, share=True)


# def transcribe_audio(audio_path):
#   # 1. Prevent NoneType error when microphone is empty
#   if audio_path is None:
#     return "No audio recorded yet."

  # 2. Process with Whisper (expects a file path string)
  # client = openai.OpenAI()
  # audio_file = open(audio_path, "rb")
  # transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
  # return transcription.text

#   return f"Successfully received file at: {audio_path}"


# demo = gr.Interface(
#     fn=transcribe_audio,
#     inputs=gr.Audio(sources=["microphone"], type="filepath"),
#     outputs="text",
# )

# demo.launch()
