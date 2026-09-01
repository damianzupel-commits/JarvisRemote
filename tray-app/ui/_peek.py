import pathlib

base = pathlib.Path(__file__).resolve().parent
out = base / "_peek_out"
out.mkdir(exist_ok=True)

for name in ["main_window.py", "chat_view.py"]:
    text = (base / name).read_text(encoding="utf-8")
    chunk = 2200
    for i in range(0, len(text), chunk):
        part = text[i : i + chunk]
        (out / f"{name}.{i // chunk:02d}.txt").write_text(part, encoding="utf-8")
    (out / f"{name}.count.txt").write_text(str(len(text)), encoding="utf-8")