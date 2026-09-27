"""
sensor.py -- INuiSensor COM binding (Kinect for Windows SDK 1.8).

The flat Kinect10.dll API (nui.py) exposes only 25 functions. The real capability
surface lives on the INuiSensor COM interface, which the flat API never reaches:

    31  NuiGetForceInfraredEmitterOff     <- projector on/off
    32  NuiSetForceInfraredEmitterOff        turning it off makes the IR camera
                                             a passive 830nm NIR camera
    33  NuiAccelerometerGetCurrentReading <- raw 3-axis g, not the 1-degree tilt

Vtable indices are taken from the SDK's own NuiSensor.h (struct INuiSensorVtbl),
not guessed.

SAFETY: calling a wrong vtable slot means calling an arbitrary function pointer.
So `verify()` checks two harmless slots with known answers -- NuiInstanceIndex()
must be 0 and NuiStatus() must be S_OK -- before anything that touches hardware.
If the layout is wrong that fails loudly instead of crashing the process.
"""
import ctypes as C
from ctypes import wintypes as W
import numpy as np
from nui import (NUI_IMAGE_FRAME, NUI_LOCKED_RECT, RES_DIMS,
                 _dll, _hr, _vtbl, _LockRect, _UnlockRect,
                 _VT_LOCKRECT, _VT_UNLOCKRECT)

# --- INuiSensorVtbl indices, from NuiSensor.h -------------------------------
V_RELEASE          = 2
V_INITIALIZE       = 3
V_SHUTDOWN         = 4
V_STREAM_OPEN      = 6
V_STREAM_NEXT      = 9
V_STREAM_RELEASE   = 10
V_ELEV_SET         = 14
V_ELEV_GET         = 15
V_INSTANCE_INDEX   = 22
V_STATUS           = 26
V_GET_IR_OFF       = 31
V_SET_IR_OFF       = 32
V_ACCELEROMETER    = 33

_F_void_l   = C.WINFUNCTYPE(C.c_long, C.c_void_p)
_F_void_i   = C.WINFUNCTYPE(C.c_int,  C.c_void_p)
_F_void_b   = C.WINFUNCTYPE(C.c_int,  C.c_void_p)
_F_init     = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_uint32)
_F_shutdown = C.WINFUNCTYPE(None,     C.c_void_p)
_F_open     = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int32, C.c_int32,
                            C.c_uint32, C.c_uint32, W.HANDLE, C.POINTER(W.HANDLE))
# NOTE: the COM signature DIFFERS from the flat API of the same name.
#   flat : NuiImageStreamGetNextFrame(HANDLE, DWORD, NUI_IMAGE_FRAME **)  <- ptr-to-ptr
#   COM  : NuiImageStreamGetNextFrame(This, HANDLE, DWORD, NUI_IMAGE_FRAME *) <- caller-allocated
# Passing a ptr-to-ptr here makes the SDK write 48 bytes over an 8-byte variable
# and segfaults the interpreter. Same for ReleaseFrame.
_F_next     = C.WINFUNCTYPE(C.c_long, C.c_void_p, W.HANDLE, C.c_uint32,
                            C.POINTER(NUI_IMAGE_FRAME))
_F_relframe = C.WINFUNCTYPE(C.c_long, C.c_void_p, W.HANDLE,
                            C.POINTER(NUI_IMAGE_FRAME))
_F_setirq   = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.c_int)

class Vector4(C.Structure):
    _fields_ = [("x", C.c_float), ("y", C.c_float),
                ("z", C.c_float), ("w", C.c_float)]

_F_accel = C.WINFUNCTYPE(C.c_long, C.c_void_p, C.POINTER(Vector4))

_dll.NuiCreateSensorByIndex.argtypes = [C.c_int, C.POINTER(C.c_void_p)]
_dll.NuiGetSensorCount.argtypes = [C.POINTER(C.c_int)]


class Sensor:
    """INuiSensor wrapper. Use verify() before trusting any call."""

    def __init__(self, index=0):
        p = C.c_void_p()
        _hr(_dll.NuiCreateSensorByIndex(C.c_int(index), C.byref(p)),
            "NuiCreateSensorByIndex")
        self.p = p
        self._streams = {}
        self._initialised = False

    def _call(self, idx, functype):
        return _vtbl(self.p, idx, functype)

    # ---- safety gate ------------------------------------------------------
    def verify(self):
        """Prove the vtable layout before calling anything that acts on hardware."""
        idx = self._call(V_INSTANCE_INDEX, _F_void_i)(self.p)
        st = self._call(V_STATUS, _F_void_l)(self.p)
        if idx != 0:
            raise RuntimeError("vtable check failed: NuiInstanceIndex()=%d, expected 0" % idx)
        if st != 0:
            raise RuntimeError("sensor not ready: NuiStatus()=0x%08X" % (st & 0xFFFFFFFF))
        return {"instance_index": idx, "status": st}

    # ---- the capabilities the flat API cannot reach ------------------------
    def get_ir_emitter_off(self):
        return bool(self._call(V_GET_IR_OFF, _F_void_b)(self.p))

    def set_ir_emitter_off(self, off):
        _hr(self._call(V_SET_IR_OFF, _F_setirq)(self.p, C.c_int(1 if off else 0)),
            "NuiSetForceInfraredEmitterOff")

    def accelerometer(self):
        """Raw 3-axis reading in g. Gravity shows as ~1.0 on the down axis."""
        v = Vector4()
        _hr(self._call(V_ACCELEROMETER, _F_accel)(self.p, C.byref(v)),
            "NuiAccelerometerGetCurrentReading")
        return (v.x, v.y, v.z, v.w)

    def elevation_angle(self):
        a = C.c_long(0)
        _hr(self._call(V_ELEV_GET, C.WINFUNCTYPE(C.c_long, C.c_void_p,
                                                 C.POINTER(C.c_long)))(self.p, C.byref(a)),
            "NuiCameraElevationGetAngle")
        return a.value

    # ---- streaming --------------------------------------------------------
    def initialize(self, flags):
        _hr(self._call(V_INITIALIZE, _F_init)(self.p, C.c_uint32(flags)),
            "INuiSensor::NuiInitialize")
        self._initialised = True

    def open_stream(self, image_type, resolution, stream_flags=0, frame_limit=2):
        h = W.HANDLE()
        _hr(self._call(V_STREAM_OPEN, _F_open)(
            self.p, C.c_int32(image_type), C.c_int32(resolution),
            C.c_uint32(stream_flags), C.c_uint32(frame_limit), None, C.byref(h)),
            "INuiSensor::NuiImageStreamOpen")
        self._streams[image_type] = (h, resolution)
        return h

    def grab(self, image_type, timeout_ms=2000, dtype=np.uint16):
        h, res = self._streams[image_type]
        fr = NUI_IMAGE_FRAME()                      # caller allocates; SDK fills it
        _hr(self._call(V_STREAM_NEXT, _F_next)(self.p, h, C.c_uint32(timeout_ms),
                                               C.byref(fr)),
            "INuiSensor::NuiImageStreamGetNextFrame")
        try:
            tex = fr.pFrameTexture
            # A frame can arrive with no data: the HRESULT is non-negative but the
            # texture pointer is NULL. Dereferencing it segfaults the interpreter.
            if not tex:
                raise OSError("frame %d carried a null texture (no data)" % fr.dwFrameNumber)
            lr = NUI_LOCKED_RECT()
            _hr(_vtbl(tex, _VT_LOCKRECT, _LockRect)(tex, 0, C.byref(lr), None, 0),
                "LockRect")
            try:
                raw = C.string_at(lr.pBits, lr.size)
                w, hgt = RES_DIMS[res]
                arr = np.frombuffer(raw, dtype=dtype)
                if arr.size == w * hgt:
                    arr = arr.reshape(hgt, w)
                return arr.copy(), fr.dwFrameNumber
            finally:
                _vtbl(tex, _VT_UNLOCKRECT, _UnlockRect)(tex, 0)
        finally:
            self._call(V_STREAM_RELEASE, _F_relframe)(self.p, h, C.byref(fr))

    def shutdown(self):
        if self._initialised:
            self._call(V_SHUTDOWN, _F_shutdown)(self.p)
            self._initialised = False

    def release(self):
        self.shutdown()
        if self.p:
            self._call(V_RELEASE, _F_void_i)(self.p)
            self.p = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.release()
