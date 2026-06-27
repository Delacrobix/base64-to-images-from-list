# decode-images

Personal script for decoding base64 data URI images into actual image files (JPEG, WebP, or PNG).

Useful when Claude or another LLM returns images as inline data URIs or you copy images as data URIs, paste into the input file, and get real image files back.

## Usage

```
decode-images
```

The script is fully interactive:

1. Creates `decode_input.txt` in your current directory and opens it in your editor
2. Paste one or more data URI blocks in this format:

```
[screenshot]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...>
[diagram]:    <data:image/png;base64,/9j/4AAQSkZJRgABAQAAAQAB...>
```

3. Save and close the editor
4. Select output format, quality, and optional subfolder
5. Images are saved to your current directory (or subfolder)

## Requirements

```
pip install Pillow
```
