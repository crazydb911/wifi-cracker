# runner-initrd 重打包（內嵌 regulatory.db）

Alpine linux-lts 6.18+ 的 cfg80211 需要 signed regulatory.db(+.p7s) 才准設國家域；
缺檔則永遠 country 00，5GHz 全頻 no-IR（禁止發射）。

重打包（Mac 上，initrd 本體在 /Users/tongbao/vmbuild/vmbuild/runner-initrd）：

    mkdir /tmp/ird && cd /tmp/ird
    gzip -dc /Users/tongbao/vmbuild/vmbuild/runner-initrd | cpio -idm
    mkdir -p lib/firmware
    cp <本目錄>/regulatory.db <本目錄>/regulatory.db.p7s lib/firmware/
    find . | cpio -o -H newc | gzip > /tmp/runner-initrd-new
    cp /tmp/runner-initrd-new /Users/tongbao/vmbuild/vmbuild/runner-initrd

開機後 initrd 的 /init 用 insmod 載 cfg80211 → 內核直接讀 initrd 內
/lib/firmware/regulatory.db（簽章核對過 X.509 內建鑰）→ db 就緒。
app 每輪 preamble `iw reg set TW` → country TW: DFS-FCC 生效，
ch36-48 可發射（hcxdumptool 5G 後綴是 b: `-c 36b`，不是 a！）。
