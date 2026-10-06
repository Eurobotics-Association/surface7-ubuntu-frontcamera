/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <gst/gst.h>
#include <gst/gstdevice.h>
#include <gst/gstdevicemonitor.h>

#define CAMERA_LABEL "Surface Pro 7 Front Camera"
#define EXPECTED_BUFFERS 5

static GstPadProbeReturn
count_buffer(GstPad *pad, GstPadProbeInfo *info, gpointer data)
{
  guint *count = data;

  (void) pad;
  if ((GST_PAD_PROBE_INFO_TYPE(info) & GST_PAD_PROBE_TYPE_BUFFER) != 0)
    (*count)++;
  return GST_PAD_PROBE_OK;
}

static GstDevice *
find_camera(GstDeviceMonitor *monitor)
{
  GList *devices = gst_device_monitor_get_devices(monitor);
  GList *entry;
  GstDevice *camera = NULL;

  for (entry = devices; entry != NULL; entry = entry->next) {
    GstDevice *device = GST_DEVICE(entry->data);
    gchar *name = gst_device_get_display_name(device);

    if (g_strcmp0(name, CAMERA_LABEL) == 0)
      camera = gst_object_ref(device);
    g_free(name);
    if (camera != NULL)
      break;
  }

  g_list_free_full(devices, gst_object_unref);
  return camera;
}

int
main(int argc, char **argv)
{
  GstDeviceMonitor *monitor = NULL;
  GstDevice *camera = NULL;
  GstElement *pipeline = NULL;
  GstElement *source = NULL;
  GstElement *sink = NULL;
  GstPad *sink_pad = NULL;
  GstBus *bus = NULL;
  GstMessage *message = NULL;
  GError *error = NULL;
  gchar *debug = NULL;
  guint buffers = 0;
  gboolean monitor_started = FALSE;
  gboolean elements_added = FALSE;
  int result = 1;

  gst_init(&argc, &argv);
  monitor = gst_device_monitor_new();
  gst_device_monitor_add_filter(monitor, "Video/Source", NULL);
  if (!gst_device_monitor_start(monitor)) {
    g_printerr("DEVICE_MONITOR_START_FAILED\n");
    goto cleanup;
  }
  monitor_started = TRUE;

  camera = find_camera(monitor);
  if (camera == NULL) {
    g_printerr("CAMERA_NOT_ENUMERATED\n");
    goto cleanup;
  }

  pipeline = gst_pipeline_new("surface7-provider-capture-test");
  source = gst_device_create_element(camera, "source");
  sink = gst_element_factory_make("fakesink", "sink");
  if (pipeline == NULL || source == NULL || sink == NULL) {
    g_printerr("PIPELINE_ELEMENT_CREATE_FAILED\n");
    goto cleanup;
  }

  g_object_set(sink, "num-buffers", EXPECTED_BUFFERS,
      "sync", FALSE, "async", FALSE, NULL);
  sink_pad = gst_element_get_static_pad(sink, "sink");
  if (sink_pad == NULL) {
    g_printerr("SINK_PAD_UNAVAILABLE\n");
    goto cleanup;
  }
  gst_pad_add_probe(sink_pad, GST_PAD_PROBE_TYPE_BUFFER,
      count_buffer, &buffers, NULL);
  gst_bin_add_many(GST_BIN(pipeline), source, sink, NULL);
  elements_added = TRUE;

  if (!gst_element_link(source, sink)) {
    g_printerr("PIPELINE_LINK_FAILED\n");
    goto cleanup;
  }

  bus = gst_element_get_bus(pipeline);
  if (gst_element_set_state(pipeline, GST_STATE_PLAYING) ==
      GST_STATE_CHANGE_FAILURE) {
    g_printerr("PIPELINE_PLAY_FAILED\n");
    goto cleanup;
  }

  message = gst_bus_timed_pop_filtered(bus, 15 * GST_SECOND,
      GST_MESSAGE_EOS | GST_MESSAGE_ERROR);
  if (message == NULL) {
    g_printerr("CAPTURE_TIMEOUT\n");
    goto cleanup;
  }
  if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR) {
    gst_message_parse_error(message, &error, &debug);
    g_printerr("PIPELINE_ERROR: %s\n",
        error != NULL ? error->message : "unknown");
    if (debug != NULL)
      g_printerr("DEBUG: %s\n", debug);
    goto cleanup;
  }

  g_print("EOS=yes\nBUFFERS=%u\n", buffers);
  result = buffers == EXPECTED_BUFFERS ? 0 : 2;

cleanup:
  g_clear_error(&error);
  g_free(debug);
  if (message != NULL)
    gst_message_unref(message);
  if (pipeline != NULL)
    gst_element_set_state(pipeline, GST_STATE_NULL);
  if (bus != NULL)
    gst_object_unref(bus);
  if (sink_pad != NULL)
    gst_object_unref(sink_pad);
  if (!elements_added && source != NULL)
    gst_object_unref(source);
  if (!elements_added && sink != NULL)
    gst_object_unref(sink);
  if (pipeline != NULL)
    gst_object_unref(pipeline);
  if (camera != NULL)
    gst_object_unref(camera);
  if (monitor != NULL) {
    if (monitor_started)
      gst_device_monitor_stop(monitor);
    gst_object_unref(monitor);
  }
  return result;
}
