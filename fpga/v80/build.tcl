if {$argc != 3} {error "usage: build.tcl <AMR v80_base> <monolithic VmeCoreMiniAxi.sv> <new output directory>"}
lassign $argv platform rtl out
set platform [file normalize $platform]
set rtl [file normalize $rtl]
set out [file normalize $out]
set src [file dirname [file normalize [info script]]]
set proj_name coral_v80
if {[file exists $out]} {error "Choose a new output directory: $out"}
create_project $proj_name $out -part xcv80-lsva4737-2MHP-e-S
set_property board_part xilinx.com:v80:part0:2.0 [current_project]
set_property segmented_configuration true [current_project]
set_property ip_repo_paths [file join $platform ip] [current_project]
update_ip_catalog

add_files -norecurse [list $rtl $src/coralnpu_v80.v]
set_property verilog_define {FPGA_XILINX FPGA_VERSAL_HBM USE_GENERIC VLEN_128 TB_SUPPORT ZVE32F_ON ZVT_ON ZVTBF16FMM_ON ZVTI16I32MM_ON} [current_fileset]
set f [open $platform/xdc/impl.pins.xdc r]
set pins [read $f]
close $f
foreach {signal expected actual} {
    hbm_ref_clk_0_clk_p N18 N19
    hbm_ref_clk_0_clk_n N19 N18
    hbm_ref_clk_1_clk_p N38 N37
    hbm_ref_clk_1_clk_n N37 N38
} {
    set pattern [format {PACKAGE_PIN %s( +\} \[get_ports )"%s"\]} $expected $signal]
    set replacement [format {PACKAGE_PIN %s\1{%s[0]}]} $actual $signal]
    if {[regsub -all $pattern $pins $replacement pins] != 1} {error "Unexpected AMR pin assignment for $signal"}
}
set f [open $out/v80.pins.xdc w]
puts -nonewline $f $pins
close $f
add_files -fileset constrs_1 $out/v80.pins.xdc
set_property USED_IN_SYNTHESIS false [get_files v80.pins.xdc]

source $platform/scripts/config_bd.tcl
current_bd_instance /PF1
set core [create_bd_cell -type module -reference coralnpu_v80 coral]
set core_bus [get_bd_intf_pins coral/s_axi]
set_property -dict {CONFIG.NUM_MI 3 CONFIG.NUM_CLKS 2} [get_bd_cells smartconnect_pf1]
connect_bd_intf_net [get_bd_intf_pins smartconnect_pf1/M01_AXI] $core_bus
set clk [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wizard coral_clock]
set_property -dict [list CONFIG.PRIM_IN_FREQ 100 CONFIG.PRIM_SOURCE No_buffer \
    CONFIG.CLKOUT_REQUESTED_OUT_FREQUENCY {25,100,100,100,100,100,100} \
    CONFIG.USE_LOCKED true CONFIG.USE_RESET false] $clk
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset coral_reset]

connect_bd_net [get_bd_pins s_axi_aclk] [get_bd_pins coral_clock/clk_in1]
connect_bd_net [get_bd_pins s_axi_aresetn] [get_bd_pins coral_reset/ext_reset_in]
connect_bd_net [get_bd_pins coral_clock/clk_out1] [get_bd_pins coral/s_axi_aclk] [get_bd_pins smartconnect_pf1/aclk1] [get_bd_pins coral_reset/slowest_sync_clk]
connect_bd_net [get_bd_pins coral_clock/locked] [get_bd_pins coral_reset/dcm_locked]
connect_bd_net [get_bd_pins coral_reset/peripheral_aresetn] [get_bd_pins coral/s_axi_aresetn]
set id_gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio design_id]
set_property -dict {CONFIG.C_GPIO_WIDTH 32 CONFIG.C_ALL_INPUTS 1} $id_gpio
set id_value [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant design_id_value]
set_property -dict {CONFIG.CONST_WIDTH 32 CONFIG.CONST_VAL 1129205810} $id_value
connect_bd_net [get_bd_pins design_id_value/dout] [get_bd_pins design_id/gpio_io_i]
connect_bd_net [get_bd_pins s_axi_aclk] [get_bd_pins design_id/s_axi_aclk]
connect_bd_net [get_bd_pins s_axi_aresetn] [get_bd_pins design_id/s_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins smartconnect_pf1/M02_AXI] [get_bd_intf_pins design_id/S_AXI]
current_bd_instance /
set seg [get_bd_addr_segs -of_objects $core_bus]
if {[llength $seg] != 1} {error "Expected one CoralNPU address segment"}
assign_bd_address -offset 0x20200100000 -range 256K -target_address_space [get_bd_addr_spaces cips/CPM_PCIE_NOC_1] $seg
set id_seg [get_bd_addr_segs PF1/design_id/S_AXI/Reg]
assign_bd_address -offset 0x20200140000 -range 4K -target_address_space [get_bd_addr_spaces cips/CPM_PCIE_NOC_1] $id_seg
foreach n {0 1 2 3} {
    exclude_bd_addr_seg -target_address_space [get_bd_addr_spaces cips/FPD_CCI_NOC_$n] $id_seg
    exclude_bd_addr_seg -target_address_space [get_bd_addr_spaces cips/FPD_CCI_NOC_$n] $seg
}
validate_bd_design
save_bd_design
set wrapper [make_wrapper -files [get_files $proj_name.bd] -top]
add_files -norecurse $wrapper
set_property top ${proj_name}_wrapper [current_fileset]
generate_target all [get_files $proj_name.bd]
launch_runs impl_1 -to_step route_design -jobs 8
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
report_timing_summary -report_unconstrained -file $out/timing.rpt
report_cdc -file $out/cdc.rpt
report_drc -file $out/drc.rpt
report_utilization -file $out/utilization.rpt
report_route_status -file $out/route.rpt
report_bus_skew -file $out/bus_skew.rpt
if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {
    error "Incomplete routing"
}
foreach delay {min max} {
    set p [get_timing_paths -delay_type $delay -max_paths 1]
    if {$p eq "" || [get_property SLACK $p] < 0} {error "Failed $delay timing"}
}
if {[llength [get_drc_violations -quiet -filter {SEVERITY == "Error" || SEVERITY == "Critical Warning"}]]} {error "Design rule checks failed"}
cd [get_property DIRECTORY [get_runs impl_1]]
write_device_image -force ${proj_name}_wrapper.pdi
write_hw_platform -fixed -include_bit -force $out/coral_v80.xsa
validate_hw_platform $out/coral_v80.xsa
foreach segment {boot pld} {
    file copy ${proj_name}_wrapper_${segment}.pdi $out/coral_v80_${segment}.pdi
}
