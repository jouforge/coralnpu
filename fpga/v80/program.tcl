if {$argc != 4} {error "usage: program.tcl <hw_server> <cable serial> <AMC boot PDI> <PL PDI>"}
lassign $argv server serial boot pl
foreach file [list $boot $pl] {
    if {![file isfile $file] || [file size $file] == 0} {error "Missing image: $file"}
}
open_hw_manager
connect_hw_server -url $server
set target [get_hw_targets -quiet */xilinx_tcf/Xilinx/$serial]
if {[llength $target] != 1} {error "Cannot select cable $serial"}
current_hw_target $target
open_hw_target $target
set device [get_hw_devices -quiet -filter {PART == xcv80}]
if {[llength $device] != 1} {error "Cannot select V80 on cable $serial"}
current_hw_device $device
set_property PROGRAM.FILE [file normalize $boot] $device
program_hw_devices $device
puts "Boot: [get_property PROGRAM.LOG $device]"
set_property PROGRAM.FILE [file normalize $pl] $device
program_hw_devices -skip_reset $device
puts "PL: [get_property PROGRAM.LOG $device]"
close_hw_target $target
disconnect_hw_server
close_hw_manager
