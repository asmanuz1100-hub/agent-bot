"""Image helpers: upload validation, thumbnails and product photo trimming."""
import base64, io, logging, re, threading, time
from collections import OrderedDict

def photo_content_type(content):
    """Return the actual safe image MIME type, not one inferred from a filename."""
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return 'image/webp'
    raise ValueError('unsupported_image_format')

def decode_agent_camera_image(value):
    """Decode a small camera image uploaded by the authenticated Agent Mini App."""
    if not isinstance(value,str) or len(value)>1_700_000:
        raise ValueError('Foto hajmi juda katta.')
    match=re.fullmatch(r'data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)',value)
    if not match:
        raise ValueError('Foto formati noto‘g‘ri.')
    try:
        content=base64.b64decode(match.group(2),validate=True)
    except Exception:
        raise ValueError('Foto ma’lumoti buzilgan.')
    if len(content)<128 or len(content)>1_200_000:
        raise ValueError('Foto 1.2 MB dan oshmasin.')
    actual=photo_content_type(content)
    if actual!=match.group(1):
        raise ValueError('Foto turi mos kelmadi.')
    return content

try:
    from PIL import Image as _PILImage, ImageOps as _PILImageOps
except Exception:  # Pillow missing: serve originals, everything still works
    _PILImage=None;_PILImageOps=None
THUMB_PX=320
_THUMB_CACHE=OrderedDict()
_THUMB_LOCK=threading.Lock()
_THUMB_MAX_BYTES=16_000_000
_THUMB_SIZE=0

def make_thumb(content,px=THUMB_PX):
    """Small progressive JPEG for lists and avatars (a few dozen KB instead of megabytes)."""
    if _PILImage is None:return content
    try:
        im=_PILImage.open(io.BytesIO(content))
        try:im.draft('RGB',(px*2,px*2))
        except Exception:pass
        im=_PILImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((px,px))
        out=io.BytesIO();im.save(out,'JPEG',quality=80,optimize=True,progressive=True)
        data=out.getvalue()
        return data if len(data)<len(content) else content
    except Exception:
        logging.warning('Thumbnail failed, serving original bytes=%s',len(content))
        return content

def _thumb_mem_get(key):
    with _THUMB_LOCK:
        v=_THUMB_CACHE.get(key)
        if v is not None:_THUMB_CACHE.move_to_end(key)
        return v

def _thumb_mem_put(key,data):
    global _THUMB_SIZE
    with _THUMB_LOCK:
        old=_THUMB_CACHE.pop(key,None)
        if old is not None:_THUMB_SIZE-=len(old)
        while _THUMB_CACHE and _THUMB_SIZE+len(data)>_THUMB_MAX_BYTES:
            _,ev=_THUMB_CACHE.popitem(last=False);_THUMB_SIZE-=len(ev)
        _THUMB_CACHE[key]=data;_THUMB_SIZE+=len(data)

def store_thumb(db,file_id,data):
    """Keep a ready thumbnail in memory and (when a DB is given) in photo_thumbs."""
    if not file_id or not data:return
    _thumb_mem_put(file_id,data)
    if db is None:return
    try:
        db.execute('INSERT INTO photo_thumbs(file_id,data,ts) VALUES(?,?,?) ON CONFLICT(file_id) DO NOTHING',
                   (file_id,data,int(time.time())))
        db.commit()
    except Exception:
        logging.warning('photo_thumbs write failed')
        try:db.rollback()
        except Exception:pass

def trim_product_image(content,px=1080,threshold=240,margin=.04):
    """Mahsulot rasmi kichik ikonkada yirik ko'rinsin: oq/shaffof chetlarni kesib, oq fonli kvadrat JPEG qiladi."""
    if _PILImage is None:return content
    try:
        im=_PILImage.open(io.BytesIO(content))
        im=_PILImageOps.exif_transpose(im).convert('RGBA')
        bg=_PILImage.new('RGBA',im.size,'white');bg.alpha_composite(im);im=bg.convert('RGB')
        small=im.copy();small.thumbnail((400,400))
        box=small.convert('L').point(lambda v:255 if v<threshold else 0).getbbox()
        if box:
            sx=im.width/small.width;sy=im.height/small.height
            im=im.crop((int(box[0]*sx),int(box[1]*sy),min(im.width,int(box[2]*sx+1)),min(im.height,int(box[3]*sy+1))))
        side=int(max(im.width,im.height)*(1+2*margin))
        square=_PILImage.new('RGB',(side,side),'white')
        square.paste(im,((side-im.width)//2,(side-im.height)//2))
        square.thumbnail((px,px))
        out=io.BytesIO();square.save(out,'JPEG',quality=88,optimize=True,progressive=True)
        return out.getvalue()
    except Exception:
        logging.warning('Product image trim failed, keeping original bytes=%s',len(content))
        return content
