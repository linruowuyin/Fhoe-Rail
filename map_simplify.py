import os
import json

def round_floats(data):
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = round_floats(value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            data[i] = round_floats(item)
    elif isinstance(data, float):
        data = round(data, 2)
    return data

def process_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            json_data = json.load(f)
            rounded_data = round_floats(json_data)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(rounded_data, f, indent=4, ensure_ascii=False)
        except json.JSONDecodeError:
            print(f"Error decoding JSON in file: {file_path}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_dir = os.path.join(script_dir, "map")
    
    if not os.path.exists(map_dir):
        print("The 'map' directory does not exist in the current folder.")
        return
    
    json_files = [f for f in os.listdir(map_dir) if f.endswith('.json')]
    
    for json_file in json_files:
        file_path = os.path.join(map_dir, json_file)
        process_json_file(file_path)
        print(f"Processed: {file_path}")

if __name__ == "__main__":
    main()
