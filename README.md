# <div align="center">Testing and Improving the Correctness of Wi-Fi Frame Injection</div>

<a id="id-intro"></a>
# 1. Introduction

This repository contains a script to test the correctness of Wi-Fi frame injection. Summarized,
we found that commodity Wi-Fi dongles may improperly inject frames under certain conditions,
which may interfere with scripts, experiments, or security tests. To overcome (some of) these
issues, we updated the Linux kernel and [RadioTap](https://www.radiotap.org/) standard. Our
updates are part of the Linux kernel since v5.11 and are part of Scapy since v2.4.3.

**To more reliably inject Wi-Fi frames, use the following RadioTap header in [Scapy](https://scapy.net/):**

	# Use the following RadoTap flags for more reliable and correct frame injection
	radiotap = RadioTap(present="TXFlags", TXFlags="NOSEQ+ORDER")

	# Example frame injection using the above RadioTap header
	dot11 = Dot11(addr1="00:11:22:33:44")/Dot11Deauth(reason=7)
	sendp(radiotap/dot11)

Notice how the `NOSEQ` and `ORDER` transmission flags (TXFlags) are set. By setting these
flags, the sequence number of injected frames isn't modified, and injected frames are not
reordered relative to each other, respectively. Note that these flags are only adhered to
from Linux kernel 5.11 and above.

Unfortunately, **drivers or network cards may still overwrite fields of injected Wi-Fi frames**.
To test whether frames are properly injected, you can use the script in this repository.

Be sure to also see our notes on the [acknowledgement behavior](#id-acks) of interfaces
in monitor mode, and how to inject frames with the [More Fragments (MF) flag](#id-more-fragments).

For further details, see our paper [**Testing and Improving the Correctness of Wi-Fi Frame Injection**](https://papers.mathyvanhoef.com/wisec2023-wifi-injection.pdf).
If you are using our injection and RadioTap improvements, you can use the following BibTex entry
to cite the paper:

	@InProceedings{vanhoef-wisec2023-injection,
		author = {Mathy Vanhoef and Xianjun Jiao and Wei Liu and Ingrid Moerman},
		title = {Testing and Improving the Correctness of {Wi-Fi} Frame Injection},
		booktitle = {Proceedings of the 16\textsuperscript{th} ACM Conference on Security
			and Privacy in Wireless and Mobile Networks (WiSec~'23)},
		year = {2023},
		month = may,
		publisher = {ACM}
	}


<a id="id-intro"></a>
# 2. Common Injection Issues

For details on issues with frame injection on Linux, see our 6-page paper
[**Testing and Improving the Correctness of Wi-Fi Frame Injection**](https://papers.mathyvanhoef.com/wisec2023-wifi-injection.pdf).
The following is a summary of some practical issues you might encounter when using Wi-Fi
frame injection to perform experiments. We also discuss some open problems.


## 2.1. Pure vs mixed monitor mode

How a network card is configured impacts how frames are injected. For instance, it
impacts whether the network card will retransmit frames, or whether it will send
acknowledgements in response to received frames. There are two main ways in which a
Wi-Fi network interface can be used in practice on Linux: in pure monitor mode or mixed
monitor mode. This difference depends on whether virtual Wi-Fi interfaces or used or not.

What are virtual interfaces? Linux has the ability to use a network card normally, for
instance as a client or access point, while simultaneously operating the device in
monitor mode. This is implemented using
[virtual interfaces](https://github.com/vanhoefm/libwifi/blob/master/docs/linux_tutorial.md):
one virtual interface implements the usual client or AP behavior, while a second
virtual interface can be used to monitor and inject Wi-Fi frames. This makes it possible to
[reuse client or AP functionality](https://github.com/domienschepers/wifi-framework)
in experiments, to then inject custom frames when needed.

When the network card is only used by (virtual) interfaces in monitor mode, then we
say that the network card is operating in **pure monitor mode**. When the network card
is used by one or more (virtual) interfaces in any other non-monitor mode (e.g. client
or AP mode), and is also by one or more (virtual) interfaces in monitor mode, then we
say that the network card is operating in **mixed monitor mode**. In case of mixed monitor
mode, the term **non-monitor interface(s)** refers to the interfaces that are operating
in client or access point mode (or any other non-monitor mode).


<a id="id-acks"></a>
## 2.2. Acknowledgements

**Acknowledgements in pure monitor mode**: most network cards will not acknowledge frames
when used in pure monitor mode. This can be problematic in certain experiments. For
instance, the Hostapd daemon on Linux, which implements Access Point (AP) functionality,
requires that the association response is acknowledged. If the association response is not
acknowledged, Hostapd will disconnect the client from the AP. Since it's impossible to send
acknowledgement frames fast enough in user space, this makes it impossible to test
Hostapd on Linux when manually implementing the association procedure in user space.

One way to overcome this problem is to put the network mode into _active monitor mode_
using the iw tool:

	sudo ifconfig wlan0 down
	sudo iw wlan0 set type monitor
	sudo iw wlan0 set monitor active
	sudo ifconfig wlan0 up

However, at the time of writing, only the `mt76` and `mt7601u` support active monitor
mode. You can see which drivers support active monitor mode by
[seeing which drivers advertise the `NL80211_FEATURE_ACTIVE_MONITOR` feature](https://elixir.bootlin.com/linux/latest/A/ident/NL80211_FEATURE_ACTIVE_MONITOR).

A second alternative to ensure that frames are acknowledged is to use mixed monitor mode with
one virtual interface in client or AP mode, and the second interface in monitor mode.
Ideally, a virtual AP interface is used because you can more easily ensure it stays on the
same channel. You can use the following code for this:

	sudo ifconfig wlan0 down
	sudo iw wlan0 interface add wlan0mon type monitor
	sudo iw wlan0 set type __ap
	sudo ifconfig wlan0 up
	sudo iw wlan0 ap start somessid 2462 10000 1 head 80000000000000000000c4e984dbfb7bc4e984dbfb7b0000000000000000000064000000
	sudo ifconfig wlan0mon up

In the "ap start" command, replace the two repeating strings `c4e984dbfb7b` with the MAC
address of the wlan0 interface. In the above case, `wlan0` is put into AP mode so that
frames towards its MAC address will be acknowledged. The other virtual interface `wlan0mon`
can then be used to monitor Wi-Fi traffic and to inject Wi-Fi frames. For more information
on the `ap start` command see the [`start_ap` function in libwifi](https://github.com/vanhoefm/libwifi/blob/master/wifi.py).

A last alternative is to use a Wi-Fi dongle that always actively acknowledges frames, even
when it doesn't implement the above _active monitor mode_. From my experience, this is
often the case with Atheros/Qualcomm dongles, e.g., dongles that use the driver `ath9k_htc`.
See also the [`ath_masker` project](https://github.com/vanhoefm/ath_masker) to even acknowledge
MAC addresses that are spoofed, where further background on the mechanisms that this is based
on is explained in [Unmasking a Spoofed MAC Address (CVE-2013-4579)](https://www.mathyvanhoef.com/2013/11/unmasking-spoofed-mac-address.html)


<a id="id-more-fragments"></a>
## 2.3. More Fragments (MF) flag

Some network cards, such as the the Intel AC-3160 and those based on the RT5572 chipset did not
properly transmit injected frames with the More Fragments (MF) flag set. This can be solved by,
after injecting the frame with the MF flag set, immediately injecting a dummy frame
_without_ the MF flag. With the RT5572 chipset, this dummy frame must also have the same QoS TID
as the injected frame, but all other fields of the dummy frame did not matter.

The above workaround is implemented in our injection tests. In particular, the driver
of the network cards is detected, and the dummy frame is injected when needed:

	# Workaround to properly inject fragmented frames (and prevent it from blocking Tx queue).
	driver_out = get_device_driver(iface_out)
	sout.mf_workaround = driver_out in ["iwlwifi", "ath9k_htc", "rt2800usb"]
	if sout.mf_workaround:
		log(WARNING, f"Detected {driver_out}, using workaround to reliably inject fragmented frames.")

	...

	# Note: this workaround for Intel is only needed if the fragmented frame is injected using
	#       valid MAC addresses. But for simplicity just execute it after any fragmented frame.
	if sout.mf_workaround and toinject.FCfield & Dot11(FCfield="MF").FCfield != 0:
		fix = Dot11(type=p.type, subtype=p.subtype)
		# Note: for the RT5572 the workaround is always needed. Additionally, we need to send
		#       the dummy frame using the same QoS TID. Just use the same QoD TID for all devices.
		if Dot11QoS in p:
			fix = fix/Dot11QoS(TID=p[Dot11QoS].TID)
		sout.send(RadioTap(present="TXFlags", TXFlags="NOSEQ+ORDER")/fix)
		log(STATUS, f"Sending dummy frame after injecting frame with MF flag set: {repr(fix)}")

Summarized, when injecting frames with the More Fragments flag, you may have to implement
a similar workaround where a dummy frame is injected afterwards (otherwise the frame with
the MF flag may not be properly transmitted).


## 2.4. Other issues

- The order of injected frames may also be changed in both pure and mixed monitor modes.
  In particular, frames with different QoS TID values, i.e., with different priorities,
  may get reordered before they are transmitted. This can be avoided by using the new
  `ORDER` TXFlag in the RadioTap header, though not all drivers may properly adhere
  to this flag.

- The Linux kernel overwrites the sequence number of injected frames in mixed monitor mode.
  This can be avoided by using the `NOSEQ` TXFlag. However, some network cards may also
  overwrite the sequence or fragment number in their driver or firmware code. To remedy
  that you would need patched driver or firmware code.

- For other examples see [our paper](https://papers.mathyvanhoef.com/wisec2023-wifi-injection.pdf).


## 2.5. Open Problems

Some known injection problems that have not yet been fixed are:

- With the `mac80211_hwsim` driver to create simulated Wi-Fi interfaces, frames with a
  spoofed sender address are not being transmitted when operating in mixed monitor mode.

- The `rt2800usb` driver, at least when combined with an RT5572 Wireless Adapter, is unable
  to inject frames that have the "More Fragment" flag set. These frames are silently dropped.
  In the meantime, this can be solved by the workaround of [injecting a dummy frame afterwards](id-more-fragments).

- The default firmware of `ath9k_htc` network cards will overwrite the sequence and
  fragment number of injected frames, both in pure and mixed monitor mode. Use
  [patched firmware](https://github.com/vanhoefm/fragattacks/tree/master/research/ath9k-firmware)
  to fix this injection issue.

- The firmware of the Intel AX200 and Intel Tiger Lake PCH CNVi WiFi crashes when injecting
  a frame with the More Fragments flag set. This happens in both pure and mixed monitor mode.

- When putting the Intel Tiger Lake PCH CNVi WiFi into pure monitor mode, you have to wait roughly
  30 seconds before it starts receiving frames. Switching back and forth between mixed managed
  and pure monitor causes it not to receive frames at all in monitor mode. It cannot inject frames
  in mixed monitor mode, at least before authentication. In pure monitor mode, it was unable to
  inject EAPOL frames and it overwrites the sequence and fragment number. Do not use this card.

- I haven't experimented with this yet, but it would be interesting to test if a network card
  in monitor mode might also reorder received frames that have a different QoS TID priority.
  If that happens, our reorder tests may not be reliable, because it may be the _monitor_
  interface that is reordering frames and not the interface that is _transmitting_ frames!


<a id="id-prerequisites"></a>
# 3. Prerequisites

The injection test tool was tested on Ubuntu 22.04. To install the required dependencies, execute:

	# Ubuntu:
	sudo apt-get update
	sudo apt-get install git macchanger net-tools virtualenv rfkill

Then clone this repository **and its submodules**, and configure a virtual python3
environment so the correct scapy library will be used:

	git clone https://github.com/vanhoefm/wifi-injection.git --recursive
	cd wifi-injection
	./pysetup.sh

The above instructions only have to be executed once. After pulling in new code it's
recommended to execute `./pysetup.sh` again so that any new Python dependencies will
be loaded. Pull in new code using:

	git update
	git submodule update


<a id="id-testing-injection"></a>
# 4. Testing Injection

You should [disable Wi-Fi in your network manager](https://github.com/vanhoefm/libwifi/blob/master/docs/linux_tutorial.md#id-disable-wifi)
so it will not interfere with the test tool. On Ubuntu, you can do this using `nmcli radio wifi off`.
Otherwise, the network manager of Ubuntu will interfere with the test tool.

We also recommend unplugging and then plugging the Wi-Fi dongle back in before running the
injection tests. Other tools might have created a virtual interface that could interfere
with the injection tests, and unplugging the dongle will remove these virtual interfaces.
If you are testing the built-in network card of your computer, consider first rebooting.

The basic execution of the test tool is as follows:

	sudo su
	source venv/bin/activate
	./test-injection.py wlan0

All possible parameters are discussed below.


## 4.1. Self-test vs. real transmission tests

If you don't have a second network card that supports monitor mode, you can perform an
injection self-test. This self-test can detect if the Linux kernel or driver interferes
with frame injection, but it cannot check the actual transmission behaviour of the
network card itself. You can perform a self-test as follows:

	./test-injection.py wlan0

If you have a second network card, that can be used to monitor the _actual_ transmission
of frames. It's strongly recommended to test frame injection with a second network card.
You can execute such a test as follows:

	./test-injection.py wlan0 wlan1

Here `wlan0` will be used to inject frames and `wlan1` will be used to see whether
injected frames are being properly transmitted by `wlan0`.

By default, the script will use channel 1 for the tests. If you want to use a different
channel you can use:

	./test-injection.py wlan0 wlan1 --channel 11

**It's strongly recommended to use a channel that is not actively used by others**.
Any background noise will reduce the reliability of the tests. In case all channels
are actively used, the only alternative is to run the test multiple times.


## 4.2. Active pure monitor mode

By default pure monitor mode injection will be tested. You can also test whether the
network card supports active pure monitor mode, in which case it should acknowledge
frames sent towards it. You can test active pure monitor mode injection as follows:

	./test-injection.py wlan0 [wlan1] --active [--channel 11]


## 4.3. Mixed monitor mode

To test whether a network card properly injects frames in _mixed monitor mode_, you
can execute one of the following two commands:

	./test-injection.py wlan0 [wlan1] --ap [--channel 11]
	./test-injection.py wlan0 [wlan1] --client [--channel 11]

The first command tests the case where `wlan0` operates in client (managed) mode
and frames are injected using the (newly created) `wlan0mon` monitor interface.
The second command is similar but puts the `wlan0` interface in AP mode.


## 4.4. Mixed monitor mode injection during or after authentication

Testing the correctness of frame injection in mixed monitor mode while a client
is (or has been) authenticated to an AP is not supported by this script. To perform
such tests, use the `--inject-test` and `--inject-test-postauth` parameters of the
[FragAttacks](https://github.com/vanhoefm/fragattacks) testing script.


## 4.5. Interpreting test results

The test script will give detailed output on which tests succeeded or failed, and will
conclude by outputting either `==> The most important tests have been passed successfully`
or a message indicating that either important tests failed or that it couldn't capture
certain injected frames.

Note that the injection scripts only test the most important behaviour. The best way
to confirm that injection is properly working in your own experiments is to used a
second monitor device and manually check if frames are properly being transmitted as
you expect.

When certain injected frames could not be captured, this may either be because of
background noise, or because the network card being tested is unable to properly inject
certain frames (e.g. the firmware of the Intel AX200 crashes when injecting fragmented
frames). It could also be that frames are in fact properly injected, but that the network
card used to monitor whether frames are injected properly (`wlan1` in the above examples)
is not reliable and is, for example, missing most frames due to background noise. Try
running the tests on a different channel as well.


## 4.6. Manual testing notes

When using Wireshark to inspect the injection behaviour of a device it is recommended
to use a second device in pure monitor mode to see how frames are being transmitted.

In case you open the interface used to inject frames then you will see injected frames
twice: (1) first you see the frame as injected by whatever tool is sending it, and then
(2) a second time by how the frame was transmitted by the driver. These two frames may
slightly differ if the kernel overwrote certain fields. If you only see an injected
frame once it may have been dropped by the kernel.


# 5. Personal Notes

- TODO: Double-check the behaviour of the AWUS036ACM when injecting a frame with the
  More Fragment (MF) flag set. Earlier, this README said that this dongle had trouble
  injecting this frame, but the paper mentioned it was the RT5572 chipsets.
- Note that the nl80211 command `NL80211_CMD_FRAME` only sends management frames.
  To inject any frame toghether with a preceeding Radiotap header, the Linux function
  `ieee80211_monitor_start_xmit` is used, which is only called for an interface that
  is in monitor mode. TODO: Further confirm this.
