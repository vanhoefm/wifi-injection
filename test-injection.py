#!/usr/bin/env python3
# Copyright (c) 2020-2023, Mathy Vanhoef <mathy.vanhoef@kulueven.be>
#
# This code may be distributed under the terms of the BSD license.
# See README for more details.

from libwifi import *
import argparse, time, subprocess

def main():
	parser = argparse.ArgumentParser(description="Test packet injection properties of a device.")
	parser.add_argument('inject', help="Interface to use to inject frames.")
	parser.add_argument('monitor', nargs='?', help="Interface to use to monitor for frames.")
	parser.add_argument('--channel', type=int, default=1, help="Channel to use for injection tests.")
	parser.add_argument('--debug', type=int, default=0, help="Debug output level.")
	parser.add_argument('--active', action='store_true', help="Put inject interface in active monitor mode.")
	parser.add_argument('--ap', action='store_true', help="Add a virtual AP interface on the inject interface.")
	parser.add_argument('--client', action='store_true', help="Add a virtual client interface on the inject interface.")
	parser.add_argument('--skip-mf', action='store_true', help="Skip injection of frames with More Fragments flag.")
	options = parser.parse_args()

	if options.active + options.ap + options.client > 1:
		log(ERROR, "You cannot use --active, --ap, or --client simultaneously")
		quit(1)

	log(STATUS, "Note: disable Wi-Fi in your network manager so it doesn't interfere with this script")
	peermac = "00:11:22:33:44:55"
	subprocess.check_output(["rfkill", "unblock", "wifi"])

	# Parse remaining options
	change_log_level(-options.debug)

	# Configure any virtual interfaces that must be added/configured. Usually the virtual AP,
	# client, mesh, whatever interface, must be assigned the used MAC address. Because of this,
	# we turn the given inject interface into the virtual interface, and create a saperate
	# monitor interface for frame injection.
	# TODO: We should look if there are any other virtual interface that might interfere.
	if options.ap or options.client:
		iface_virt = options.inject
		iface_mon = options.inject[:12] + "mon"
		subprocess.call(["iw", iface_mon, "del"], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
		subprocess.check_output(["iw", options.inject, "interface", "add", iface_mon, "type", "monitor"])
		options.inject = iface_mon
	if options.ap:		
		if not set_ap_mode(iface_virt):
			log(ERROR, f"Interface {iface_virt} doesn't support AP mode")
			quit(1)
		start_ap(iface_virt, options.channel, interval=10000)
		log(STATUS, f"Interface {iface_virt} was put into AP mode, and {iface_mon} was created to inject frames.")

	# Configure the injection interface
	set_monitor_mode(options.inject, up=False)
	if options.active and not set_monitor_active(options.inject):
		log(ERROR, f"Failed to enable active monitor mode for {options.inject}")
		quit(1)
	subprocess.check_output(["ifconfig", options.inject, "up"])
	if not options.ap and not options.client:
		set_channel(options.inject, options.channel)

	# Some configuration of the virtual interface needs to be done after the injection interface
	# was put on the correct channel.
	if options.client:
		# The HOPE (there is no guarantee) is that the kernel won't change the channel of the
		# interface once we put it into client mode. The monitor interface will follow the channel
		# of whatever the client is on.
		set_managed_mode(iface_virt)
		log(STATUS, f"Interface {iface_virt} was put into client (managed) mode, and {iface_mon} was created to inject frames.")

	# Configure the monitor interface
	if options.monitor:
		set_monitor_mode(options.monitor)
		set_channel(options.monitor, options.channel)
		# The peermac isn't that essential. It's used as a backup when we can't find a neary AP,
		# and then the script will also show a warning (perhaps it should exit instead). For now,
		# just set the MAC address of the second interface, it's better than nothing.
		peermac = get_macaddress(options.monitor)

	# Star the injection tests
	try:
		test_injection(options.inject, options.monitor, peermac, skip_mf=options.skip_mf)
	except OSError as ex:
		log(ERROR, str(ex))

if __name__ == "__main__":
	main()

