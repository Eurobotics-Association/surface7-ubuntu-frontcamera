/* SPDX-License-Identifier: LGPL-2.1-or-later */
/*
 * Surface Pro 7 V4L2 loopback provider.
 *
 * The patched libcamera v4l2 provider on this host suppresses the loopback
 * node because its udev capabilities metadata describes the producer side.
 * This provider exposes only the project's labeled capture-capable loopback
 * device and leaves all other V4L2/GStreamer providers untouched.
 */

#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <linux/videodev2.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <gst/gst.h>
#include <gst/gstdevice.h>
#include <gst/gstdeviceprovider.h>

#ifndef PACKAGE
#define PACKAGE "surface7-ubuntu-frontcamera"
#endif

#ifndef VERSION
#define VERSION "0.1.0"
#endif

#define S7_CAMERA_LABEL "Surface Pro 7 Front Camera"

typedef struct _S7CameraDevice {
  GstDevice parent;
  gchar *path;
} S7CameraDevice;

typedef struct _S7CameraDeviceClass {
  GstDeviceClass parent_class;
} S7CameraDeviceClass;

typedef struct _S7CameraProvider {
  GstDeviceProvider parent;
} S7CameraProvider;

typedef struct _S7CameraProviderClass {
  GstDeviceProviderClass parent_class;
} S7CameraProviderClass;

G_DEFINE_TYPE(S7CameraDevice, s7_camera_device, GST_TYPE_DEVICE)
G_DEFINE_TYPE(S7CameraProvider, s7_camera_provider, GST_TYPE_DEVICE_PROVIDER)

static GstElement *
s7_camera_device_create_element(GstDevice *base, const gchar *name)
{
  S7CameraDevice *device = (S7CameraDevice *) base;
  GstElement *source = gst_element_factory_make("v4l2src", name);

  if (source == NULL)
    return NULL;

  g_object_set(source, "device", device->path, NULL);
  gst_util_set_object_arg(G_OBJECT(source), "io-mode", "rw");
  return source;
}

static void
s7_camera_device_finalize(GObject *object)
{
  S7CameraDevice *device = (S7CameraDevice *) object;

  g_clear_pointer(&device->path, g_free);
  G_OBJECT_CLASS(s7_camera_device_parent_class)->finalize(object);
}

static void
s7_camera_device_class_init(S7CameraDeviceClass *klass)
{
  G_OBJECT_CLASS(klass)->finalize = s7_camera_device_finalize;
  GST_DEVICE_CLASS(klass)->create_element = s7_camera_device_create_element;
}

static void
s7_camera_device_init(S7CameraDevice *device)
{
  (void) device;
}

static gboolean
s7_is_surface_loopback(const gchar *path)
{
  struct v4l2_capability capability;
  guint32 caps;
  int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);

  if (fd < 0)
    return FALSE;

  memset(&capability, 0, sizeof(capability));
  if (ioctl(fd, VIDIOC_QUERYCAP, &capability) < 0) {
    close(fd);
    return FALSE;
  }
  close(fd);

  caps = capability.device_caps ? capability.device_caps : capability.capabilities;
  return (caps & V4L2_CAP_VIDEO_CAPTURE) != 0 &&
         g_strcmp0((const gchar *) capability.driver, "v4l2 loopback") == 0 &&
         g_strcmp0((const gchar *) capability.card, S7_CAMERA_LABEL) == 0;
}

static GstDevice *
s7_make_device(const gchar *path)
{
  GstCaps *caps = gst_caps_from_string(
      "video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1");
  GstStructure *properties = gst_structure_new("surface7-v4l2-camera",
      "device.path", G_TYPE_STRING, path,
      "device.api", G_TYPE_STRING, "v4l2",
      "device.product.name", G_TYPE_STRING, S7_CAMERA_LABEL,
      NULL);
  S7CameraDevice *device = g_object_new(s7_camera_device_get_type(),
      "display-name", S7_CAMERA_LABEL,
      "device-class", "Video/Source",
      "caps", caps,
      "properties", properties,
      NULL);

  if (device != NULL)
    device->path = g_strdup(path);

  gst_caps_unref(caps);
  gst_structure_free(properties);
  return device != NULL ? GST_DEVICE(device) : NULL;
}

static GList *
s7_camera_provider_probe(GstDeviceProvider *provider)
{
  const gchar *path = g_getenv("SURFACE7_FRONT_CAMERA_DEVICE");
  GstDevice *device;

  (void) provider;
  if (path == NULL || path[0] == '\0')
    path = "/dev/video83";
  if (!s7_is_surface_loopback(path))
    return NULL;

  device = s7_make_device(path);
  return device != NULL ? g_list_append(NULL, device) : NULL;
}

static void
s7_camera_provider_class_init(S7CameraProviderClass *klass)
{
  GstDeviceProviderClass *provider_class = GST_DEVICE_PROVIDER_CLASS(klass);

  provider_class->probe = s7_camera_provider_probe;
  gst_device_provider_class_set_static_metadata(provider_class,
      "Surface Pro 7 loopback camera",
      "Video/Source",
      "Exposes only the labeled Surface Pro 7 V4L2 loopback camera",
      "Eurobotics Association");
}

static void
s7_camera_provider_init(S7CameraProvider *provider)
{
  (void) provider;
}

static gboolean
plugin_init(GstPlugin *plugin)
{
  return gst_device_provider_register(plugin,
      "surface7-v4l2-camera-provider", GST_RANK_PRIMARY,
      s7_camera_provider_get_type());
}

GST_PLUGIN_DEFINE(GST_VERSION_MAJOR, GST_VERSION_MINOR,
    surface7v4l2camera, "Surface Pro 7 V4L2 loopback device provider",
    plugin_init, VERSION, "LGPL", PACKAGE,
    "https://github.com/Eurobotics-Association/surface7-ubuntu-frontcamera")
