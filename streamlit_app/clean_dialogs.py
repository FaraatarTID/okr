p = r"c:\Users\Surface Book 2\Documents\GitHub\okr\streamlit_app\src\ui\dialogs.py"
with open(p, 'rb') as f:
    b = f.read()
if b.find(b'\x00') != -1:
    nb = b.replace(b'\x00', b'')
    with open(p, 'wb') as f:
        f.write(nb)
    print('Removed nulls')
else:
    print('No nulls')
