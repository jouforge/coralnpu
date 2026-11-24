module BUFGCE #(
    parameter string SIM_DEVICE = "VERSAL_HBM"
) (
    input  wire I,
    input  wire CE,
    output wire O
);
  logic enabled;
  always_latch if (!I) enabled = CE;
  assign O = I & enabled;
endmodule
