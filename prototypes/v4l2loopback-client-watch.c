// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Observe v4l2loopback's private CLIENT_USAGE event for one camera node.
 *
 * This is an event-observer prototype only. It does not start or stop a
 * camera pipeline and never calls VIDIOC_STREAMON. The event number and
 * payload follow the upstream v4l2loopback v0.15.4 implementation.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define V4L2_EVENT_PRI_CLIENT_USAGE \
    (V4L2_EVENT_PRIVATE_START + 0x08E00000U + 1U)

static volatile sig_atomic_t running = 1;

static void stop_watching(int signal_number)
{
    (void)signal_number;
    running = 0;
}

static long long monotonic_ms(void)
{
    struct timespec now;

    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0)
        return -1;

    return ((long long)now.tv_sec * 1000LL) +
           (now.tv_nsec / 1000000LL);
}

static int print_client_usage_event(const struct v4l2_event *event)
{
    uint32_t clients = 0;

    if (event->type != V4L2_EVENT_PRI_CLIENT_USAGE)
        return 0;

    /*
     * v4l2loopback reports the number of active capture clients. A value
     * greater than one is valid when, for example, Cheese and a browser are
     * open at the same time.
     */
    memcpy(&clients, event->u.data, sizeof(clients));
    printf("%lld ms capture_clients=%u capture_active=%u\n",
           monotonic_ms(), clients, clients > 0U ? 1U : 0U);
    fflush(stdout);
    return 0;
}

int main(int argc, char **argv)
{
    struct v4l2_event_subscription subscription = {0};
    struct v4l2_capability capability = {0};
    struct pollfd watched_fd = {0};
    const char *device;
    int fd;

    if (argc != 2) {
        fprintf(stderr, "usage: %s /dev/videoN\n", argv[0]);
        return 2;
    }
    device = argv[1];

    signal(SIGINT, stop_watching);
    signal(SIGTERM, stop_watching);

    fd = open(device, O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "open %s: %s\n", device, strerror(errno));
        return 2;
    }

    if (ioctl(fd, VIDIOC_QUERYCAP, &capability) < 0) {
        fprintf(stderr, "VIDIOC_QUERYCAP %s: %s\n", device,
                strerror(errno));
        close(fd);
        return 2;
    }
    if (strncmp((const char *)capability.driver, "v4l2 loopback",
                sizeof(capability.driver)) != 0) {
        fprintf(stderr, "%s is driven by '%s', not v4l2loopback\n", device,
                capability.driver);
        close(fd);
        return 2;
    }

    subscription.type = V4L2_EVENT_PRI_CLIENT_USAGE;
    subscription.flags = V4L2_EVENT_SUB_FL_SEND_INITIAL;
    if (ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, &subscription) < 0) {
        fprintf(stderr, "VIDIOC_SUBSCRIBE_EVENT %s: %s\n", device,
                strerror(errno));
        close(fd);
        return 3;
    }

    watched_fd.fd = fd;
    watched_fd.events = POLLPRI;
    printf("watching %s (v4l2loopback CLIENT_USAGE); Ctrl-C to stop\n",
           device);
    fflush(stdout);

    while (running) {
        int ready = poll(&watched_fd, 1, -1);

        if (ready < 0) {
            if (errno == EINTR)
                continue;
            fprintf(stderr, "poll %s: %s\n", device, strerror(errno));
            close(fd);
            return 4;
        }
        if (watched_fd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
            fprintf(stderr, "event descriptor for %s became unavailable\n",
                    device);
            close(fd);
            return 4;
        }
        if (watched_fd.revents & POLLPRI) {
            struct v4l2_event event;

            while (ioctl(fd, VIDIOC_DQEVENT, &event) == 0) {
                if (print_client_usage_event(&event) < 0) {
                    close(fd);
                    return 4;
                }
            }
            /* Nonblocking V4L2 event dequeue uses ENOENT for an empty queue. */
            if (errno != ENOENT && errno != EAGAIN &&
                errno != EWOULDBLOCK && errno != EINTR) {
                fprintf(stderr, "VIDIOC_DQEVENT %s: %s\n", device,
                        strerror(errno));
                close(fd);
                return 4;
            }
        }
    }

    close(fd);
    return 0;
}
