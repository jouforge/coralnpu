module coralnpu_v80 (
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET s_axi_aresetn" *)
    input wire s_axi_aclk,
    input wire s_axi_aresetn,
    output wire s_axi_awready,
    input wire s_axi_awvalid,
    input wire [17:0] s_axi_awaddr,
    input wire [2:0] s_axi_awprot,
    input wire [5:0] s_axi_awid,
    input wire [7:0] s_axi_awlen,
    input wire [2:0] s_axi_awsize,
    input wire [1:0] s_axi_awburst,
    input wire s_axi_awlock,
    input wire [3:0] s_axi_awcache,
    input wire [3:0] s_axi_awqos,
    input wire [3:0] s_axi_awregion,
    output wire s_axi_wready,
    input wire s_axi_wvalid,
    input wire [127:0] s_axi_wdata,
    input wire s_axi_wlast,
    input wire [15:0] s_axi_wstrb,
    input wire s_axi_bready,
    output wire s_axi_bvalid,
    output wire [5:0] s_axi_bid,
    output wire [1:0] s_axi_bresp,
    output wire s_axi_arready,
    input wire s_axi_arvalid,
    input wire [17:0] s_axi_araddr,
    input wire [2:0] s_axi_arprot,
    input wire [5:0] s_axi_arid,
    input wire [7:0] s_axi_arlen,
    input wire [2:0] s_axi_arsize,
    input wire [1:0] s_axi_arburst,
    input wire s_axi_arlock,
    input wire [3:0] s_axi_arcache,
    input wire [3:0] s_axi_arqos,
    input wire [3:0] s_axi_arregion,
    input wire s_axi_rready,
    output wire s_axi_rvalid,
    output wire [127:0] s_axi_rdata,
    output wire [5:0] s_axi_rid,
    output wire [1:0] s_axi_rresp,
    output wire s_axi_rlast
);
  wire m_awready;
  wire m_awvalid;
  wire [5:0] m_awid;
  wire m_wready;
  wire m_wvalid;
  wire m_wlast;
  wire m_bready;
  wire m_bvalid;
  wire [5:0] m_bid;
  wire [1:0] m_bresp;
  wire m_arready;
  wire m_arvalid;
  wire [5:0] m_arid;
  wire [7:0] m_arlen;
  wire m_rready;
  wire m_rvalid;
  wire [127:0] m_rdata;
  wire [5:0] m_rid;
  wire [1:0] m_rresp;
  wire m_rlast;

  reg write_active;
  reg write_response;
  reg [5:0] write_id;
  reg read_active;
  reg [5:0] read_id;
  reg [7:0] read_remaining;

  assign m_awready = !write_active && !write_response;
  assign m_wready = write_active;
  assign m_bvalid = write_response;
  assign m_bid = write_id;
  assign m_bresp = 2'b11;
  assign m_arready = !read_active;
  assign m_rvalid = read_active;
  assign m_rid = read_id;
  assign m_rdata = 128'd0;
  assign m_rresp = 2'b11;
  assign m_rlast = read_remaining == 0;

  always @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      write_active <= 0;
      write_response <= 0;
      read_active <= 0;
      write_id <= 0;
      read_id <= 0;
      read_remaining <= 0;
    end else begin
      if (m_awready && m_awvalid) begin
        write_id <= m_awid;
        write_active <= 1;
      end
      if (m_wready && m_wvalid && m_wlast) begin
        write_active   <= 0;
        write_response <= 1;
      end
      if (m_bready && m_bvalid) write_response <= 0;
      if (m_arready && m_arvalid) begin
        read_id <= m_arid;
        read_remaining <= m_arlen;
        read_active <= 1;
      end
      if (m_rready && m_rvalid) begin
        if (m_rlast) read_active <= 0;
        else read_remaining <= read_remaining - 1'b1;
      end
    end
  end

  VmeCoreMiniAxi core (
      .io_aclk(s_axi_aclk),
      .io_aresetn(s_axi_aresetn),
      .io_axi_slave_write_addr_ready(s_axi_awready),
      .io_axi_slave_write_addr_valid(s_axi_awvalid),
      .io_axi_slave_write_addr_bits_addr({14'd0, s_axi_awaddr}),
      .io_axi_slave_write_addr_bits_prot(s_axi_awprot),
      .io_axi_slave_write_addr_bits_id(s_axi_awid),
      .io_axi_slave_write_addr_bits_len(s_axi_awlen),
      .io_axi_slave_write_addr_bits_size(s_axi_awsize),
      .io_axi_slave_write_addr_bits_burst(s_axi_awburst),
      .io_axi_slave_write_addr_bits_lock(s_axi_awlock),
      .io_axi_slave_write_addr_bits_cache(s_axi_awcache),
      .io_axi_slave_write_addr_bits_qos(s_axi_awqos),
      .io_axi_slave_write_addr_bits_region(s_axi_awregion),
      .io_axi_slave_write_data_ready(s_axi_wready),
      .io_axi_slave_write_data_valid(s_axi_wvalid),
      .io_axi_slave_write_data_bits_data(s_axi_wdata),
      .io_axi_slave_write_data_bits_last(s_axi_wlast),
      .io_axi_slave_write_data_bits_strb(s_axi_wstrb),
      .io_axi_slave_write_resp_ready(s_axi_bready),
      .io_axi_slave_write_resp_valid(s_axi_bvalid),
      .io_axi_slave_write_resp_bits_id(s_axi_bid),
      .io_axi_slave_write_resp_bits_resp(s_axi_bresp),
      .io_axi_slave_read_addr_ready(s_axi_arready),
      .io_axi_slave_read_addr_valid(s_axi_arvalid),
      .io_axi_slave_read_addr_bits_addr({14'd0, s_axi_araddr}),
      .io_axi_slave_read_addr_bits_prot(s_axi_arprot),
      .io_axi_slave_read_addr_bits_id(s_axi_arid),
      .io_axi_slave_read_addr_bits_len(s_axi_arlen),
      .io_axi_slave_read_addr_bits_size(s_axi_arsize),
      .io_axi_slave_read_addr_bits_burst(s_axi_arburst),
      .io_axi_slave_read_addr_bits_lock(s_axi_arlock),
      .io_axi_slave_read_addr_bits_cache(s_axi_arcache),
      .io_axi_slave_read_addr_bits_qos(s_axi_arqos),
      .io_axi_slave_read_addr_bits_region(s_axi_arregion),
      .io_axi_slave_read_data_ready(s_axi_rready),
      .io_axi_slave_read_data_valid(s_axi_rvalid),
      .io_axi_slave_read_data_bits_data(s_axi_rdata),
      .io_axi_slave_read_data_bits_id(s_axi_rid),
      .io_axi_slave_read_data_bits_resp(s_axi_rresp),
      .io_axi_slave_read_data_bits_last(s_axi_rlast),
      .io_axi_master_write_addr_ready(m_awready),
      .io_axi_master_write_addr_valid(m_awvalid),
      .io_axi_master_write_addr_bits_addr(),
      .io_axi_master_write_addr_bits_prot(),
      .io_axi_master_write_addr_bits_id(m_awid),
      .io_axi_master_write_addr_bits_len(),
      .io_axi_master_write_addr_bits_size(),
      .io_axi_master_write_addr_bits_burst(),
      .io_axi_master_write_addr_bits_lock(),
      .io_axi_master_write_addr_bits_cache(),
      .io_axi_master_write_addr_bits_qos(),
      .io_axi_master_write_addr_bits_region(),
      .io_axi_master_write_data_ready(m_wready),
      .io_axi_master_write_data_valid(m_wvalid),
      .io_axi_master_write_data_bits_data(),
      .io_axi_master_write_data_bits_last(m_wlast),
      .io_axi_master_write_data_bits_strb(),
      .io_axi_master_write_resp_ready(m_bready),
      .io_axi_master_write_resp_valid(m_bvalid),
      .io_axi_master_write_resp_bits_id(m_bid),
      .io_axi_master_write_resp_bits_resp(m_bresp),
      .io_axi_master_read_addr_ready(m_arready),
      .io_axi_master_read_addr_valid(m_arvalid),
      .io_axi_master_read_addr_bits_addr(),
      .io_axi_master_read_addr_bits_prot(),
      .io_axi_master_read_addr_bits_id(m_arid),
      .io_axi_master_read_addr_bits_len(m_arlen),
      .io_axi_master_read_addr_bits_size(),
      .io_axi_master_read_addr_bits_burst(),
      .io_axi_master_read_addr_bits_lock(),
      .io_axi_master_read_addr_bits_cache(),
      .io_axi_master_read_addr_bits_qos(),
      .io_axi_master_read_addr_bits_region(),
      .io_axi_master_read_data_ready(m_rready),
      .io_axi_master_read_data_valid(m_rvalid),
      .io_axi_master_read_data_bits_data(m_rdata),
      .io_axi_master_read_data_bits_id(m_rid),
      .io_axi_master_read_data_bits_resp(m_rresp),
      .io_axi_master_read_data_bits_last(m_rlast),
      .io_halted(),
      .io_fault(),
      .io_wfi(),
      .io_irq(1'd0),
      .io_boot_addr(32'd0),
      .io_timer_irq(1'd0),
      .io_software_irq(1'd0),
      .io_dm_req_ready(),
      .io_dm_req_valid(1'd0),
      .io_dm_req_bits_address(32'd0),
      .io_dm_req_bits_data(32'd0),
      .io_dm_req_bits_op(2'd0),
      .io_dm_rsp_ready(1'b1),
      .io_dm_rsp_valid(),
      .io_dm_rsp_bits_data(),
      .io_dm_rsp_bits_op(),
      .io_te(1'd0)
  );
endmodule
