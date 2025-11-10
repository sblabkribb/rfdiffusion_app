import json
with open("rfdiffusion_app.ipynb", encoding="utf-8") as f:
    nb = json.load(f)
for idx, cell in enumerate(nb["cells"]):
    if cell.get("cell_type") != "code":
        continue
    if not cell.get("outputs"):
        continue
    print(f"Cell {idx} outputs:")
    for output in cell["outputs"]:
        if output.get("output_type") == "stream":
            text = ''.join(output.get("text", []))
            print(text.encode("ascii", "ignore").decode("ascii"))
        elif output.get("output_type")=="error":
            print('Error:', output.get('ename'), output.get('evalue'))
            for line in output.get('traceback', []):
                print(line.encode("ascii", "ignore").decode("ascii"))
        else:
            print(output)
    print('-'*40)
