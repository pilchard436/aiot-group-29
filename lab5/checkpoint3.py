import asyncio
import json
import socket
from google import genai
GEMINI_API_KEY = "AQ.Ab8RN6L8X9Kzcr1daof8fRpAW25RSmJ0iRF0i1Tis1iqPeDxLw"
SERVER_PORT = 8080
MAX_COMMAND_BYTES = 512
MAX_RESPONSE_BYTES = 4096
PROMPT = '''
    You are a voice assistant for a smartwatch. Interpret the user's command and
respond with a JSON object (no markdown) that calls specific functions for
the smartwatch. Available functions:
{
  "transport": {
    "protocol": "TCP socket",
    "port": 8080,
    "request": "Send one UTF-8 JSON object followed by a newline, then read one UTF-8 JSON response line.",
    "request_format": {
      "name": "function_name",
      "args": []
    },
    "response_format": {
      "ok": true,
      "result": "function result"
    },
    "error_response_format": {
      "ok": false,
      "error": "error description"
    }
  },
  "routing_instruction": "Choose a defined function when the user's request matches one of its capabilities. If the request does not match any defined function, call display_message with a concise response or explanation instead of inventing a function name.",
  "functions": [
    {
      "name": "screen_on",
      "args": [],
      "explanation": "Turn on the smartwatch OLED screen."
    },
    {
      "name": "screen_off",
      "args": [],
      "explanation": "Turn off the smartwatch OLED screen."
    },
    {
      "name": "display_time",
      "args": [],
      "explanation": "Start a live clock on the smartwatch OLED that refreshes every second until another display command or screen_off replaces it. Use the shown RTC time as the reference when converting a relative alarm interval into a clock timestamp."
    },
    {
      "name": "display_message",
      "args": [
        {
          "name": "message",
          "type": "string",
          "description": "Short text to show on the smartwatch OLED."
        }
      ],
      "explanation": "Display the supplied text message on the smartwatch screen. Use this as the fallback for any user command or request that does not match one of the other defined functions; pass a concise response or explanation as message."
    },
    {
      "name": "set_alarm",
      "args": [
        {
          "name": "hour",
          "type": "integer",
          "minimum": 0,
          "maximum": 23,
          "description": "Hour in 24-hour format, from 0 through 23."
        },
        {
          "name": "minute",
          "type": "integer",
          "minimum": 0,
          "maximum": 59,
          "description": "Minute, from 0 through 59."
        },
        {
          "name": "second",
          "type": "integer",
          "minimum": 0,
          "maximum": 59,
          "description": "Second, from 0 through 59."
        }
      ],
      "explanation": "Set a daily alarm for the absolute hour:minute:second timestamp. If the user gives a time interval, first obtain the current smartwatch time with display_time, then convert the interval to a target clock timestamp, including wraparound at midnight. Pass the resulting hour, minute, and second; never pass the interval."
    },
    {
      "name": "display_location",
      "args": [],
      "explanation": "Get and display the smartwatch's approximate current network location."
    },
    {
      "name": "display_weather",
      "args": [],
      "explanation": "Get and display current weather for the smartwatch's approximate network location."
    }
  ]
}

You should understand the user's request or question, try your best to parse
the request into one of the functions and return in the corresponding json
format.
If the request does not fit into any of the above functions, answer the
question based on your own knowledge, and use the display_message function to
display your response (return JSON with name "display_message" and args
containing your response as a string).
Since the smartwatch has a tiny screen, your response should be within 48
characters.
Always return args as a JSON array, not an object. For example, setting an
alarm for 8:00 PM must be:
{"name":"set_alarm","args":[20,0,0]}
    '''

COMMAND_ARGUMENT_NAMES = {
    "display_message": ("message",),
    "set_alarm": ("hour", "minute", "second"),
}


async def get_llm_response(prompt):
    full_response = ""

    async with genai.Client(api_key=GEMINI_API_KEY).aio as client:
        async for partial in await client.models.generate_content_stream(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            ):
            if partial.text:
                full_response += partial.text
    return full_response


def send_command(host, response_text):
    """Send the LLM's JSON command to the smartwatch and return its response."""
    command = json.loads(response_text)
    if not isinstance(command, dict) or not isinstance(
            command.get("name"), str):
        raise ValueError("LLM response must contain a command name")

    args = command.get("args")
    if isinstance(args, dict):
        argument_names = COMMAND_ARGUMENT_NAMES.get(command["name"])
        if argument_names is None:
            if args:
                raise ValueError(
                    "Command {} does not accept named arguments".format(
                        command["name"]))
            args = []
        else:
            if set(args) != set(argument_names):
                raise ValueError(
                    "Command {} requires named arguments: {}".format(
                        command["name"], ", ".join(argument_names)))
            args = [args[name] for name in argument_names]
    if not isinstance(args, list):
        raise ValueError("LLM response must contain a command name and args")
    command = {"name": command["name"], "args": args}

    request = (json.dumps(command) + "\n").encode("utf-8")
    if len(request) > MAX_COMMAND_BYTES:
        raise ValueError("Command exceeds {} bytes".format(MAX_COMMAND_BYTES))

    with socket.create_connection((host, SERVER_PORT), timeout=5) as client:
        client.settimeout(5)
        client.sendall(request)

        response_data = bytearray()
        while b"\n" not in response_data:
            chunk = client.recv(512)
            if not chunk:
                raise ConnectionError("Board closed without a response")
            response_data.extend(chunk)
            if len(response_data) > MAX_RESPONSE_BYTES:
                raise ValueError(
                    "Board response exceeds {} bytes".format(
                        MAX_RESPONSE_BYTES))

    board_response = json.loads(
        bytes(response_data).split(b"\n", 1)[0].decode("utf-8"))
    if not isinstance(board_response, dict) or not isinstance(
            board_response.get("ok"), bool):
        raise ValueError("Board returned an invalid response")
    return board_response


if __name__ == "__main__":
    board_host = "10.206.74.222".strip()
    # board_host = input("Enter the smartwatch board IP address: ").strip()
    while True:
        user_input = input("Enter your request: ")
        llm_response = asyncio.run(
            get_llm_response(f"{PROMPT}\n\nuser input:{user_input}"))
        print("LLM command:", llm_response)
        board_response = send_command(board_host, llm_response)
        if board_response["ok"]:
            print("Smartwatch:", board_response.get("result", "Command completed"))
        else:
            print("Smartwatch error:", board_response.get("error", "Unknown error"))