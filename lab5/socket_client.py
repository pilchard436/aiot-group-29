import argparse
import json
from pathlib import Path
import socket


CATALOG_PATH = Path(__file__).with_name("watch_functions.json")
MAX_RESPONSE_BYTES = 4096


def load_catalog():
    with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)

    transport = catalog.get("transport")
    functions = catalog.get("functions")
    if not isinstance(transport, dict) or not isinstance(functions, list):
        raise ValueError("Function catalog is missing transport or functions")
    if transport.get("protocol") != "TCP socket":
        raise ValueError("Catalog transport must be TCP socket")

    port = transport.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Catalog has an invalid TCP port")
    return port, functions


def _validate_args(function, args):
    expected_args = function.get("args")
    if not isinstance(expected_args, list):
        raise ValueError("Function catalog has invalid argument definitions")
    if len(args) != len(expected_args):
        raise ValueError("{} expects {} argument(s)".format(
            function["name"], len(expected_args)))

    for value, definition in zip(args, expected_args):
        if definition.get("type") == "integer":
            if type(value) is not int:
                raise TypeError("{} must be an integer".format(
                    definition["name"]))
            minimum = definition.get("minimum")
            maximum = definition.get("maximum")
            if ((minimum is not None and value < minimum)
                    or (maximum is not None and value > maximum)):
                raise ValueError("{} must be between {} and {}".format(
                    definition["name"], minimum, maximum))
        elif definition.get("type") == "string":
            if not isinstance(value, str):
                raise TypeError("{} must be text".format(definition["name"]))
        else:
            raise ValueError("Unsupported argument type in function catalog")


def send_command(host, port, function, args, timeout=5.0):
    """Send one catalog-defined JSON command and return the server response."""
    _validate_args(function, args)
    command = {
        "name": function["name"],
        "args": args,
    }
    request = (json.dumps(command) + "\n").encode("utf-8")

    with socket.create_connection((host, port), timeout=timeout) as client:
        client.settimeout(timeout)
        client.sendall(request)

        response_data = bytearray()
        while b"\n" not in response_data:
            chunk = client.recv(512)
            if not chunk:
                raise ConnectionError("ESP32 closed without a response")
            response_data.extend(chunk)
            if len(response_data) > MAX_RESPONSE_BYTES:
                raise ValueError("Response exceeds {} bytes".format(
                    MAX_RESPONSE_BYTES))

    response_line = bytes(response_data).split(b"\n", 1)[0]
    response = json.loads(response_line.decode("utf-8"))
    if not isinstance(response, dict) or not isinstance(
            response.get("ok"), bool):
        raise ValueError("ESP32 returned an invalid response")
    return response


def _prompt_args(function):
    args = []
    for definition in function.get("args", []):
        prompt = "{} ({}): ".format(
            definition["name"], definition.get("description", ""))
        while True:
            value = input(prompt)
            if definition.get("type") == "integer":
                try:
                    value = int(value)
                except ValueError:
                    print("Enter a whole number.")
                    continue
            try:
                _validate_args(
                    {"name": function["name"], "args": [definition]}, [value])
            except (TypeError, ValueError) as error:
                print(error)
                continue
            args.append(value)
            break
    return args


def run_interactive(host, port, functions, timeout):
    functions_by_name = {function["name"]: function for function in functions}
    while True:
        print("\nSmartwatch commands:")
        for index, function in enumerate(functions, start=1):
            print("  {}. {} - {}".format(
                index, function["name"], function["explanation"]))
        selection = input("Choose a number or command name (q to quit): ").strip()

        if selection.lower() in ("q", "quit", "exit"):
            return
        if selection in functions_by_name:
            function = functions_by_name[selection]
        else:
            try:
                function = functions[int(selection) - 1]
            except (ValueError, IndexError):
                print("Choose a listed command, or enter q to quit.")
                continue

        try:
            args = _prompt_args(function)
            response = send_command(
                host, port, function, args, timeout=timeout)
        except (OSError, TypeError, ValueError) as error:
            print("Request failed: {}".format(error))
            continue

        if response["ok"]:
            print("Smartwatch:", response.get("result", "Command completed"))
        else:
            print("Smartwatch error:", response.get("error", "Unknown error"))


def main():
    parser = argparse.ArgumentParser(
        description="Send JSON commands to the Lab 5 ESP32 smartwatch.")
    parser.add_argument("host", help="ESP32 IP address shown by its server")
    parser.add_argument("--port", type=int, help="TCP port (default: catalog value)")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    default_port, functions = load_catalog()
    port = default_port if args.port is None else args.port
    if not 1 <= port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.timeout <= 0:
        parser.error("timeout must be greater than zero")

    run_interactive(args.host, port, functions, args.timeout)


if __name__ == "__main__":
    main()
