/*
 * Copyright (c) 2024 Gong Chen
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire       clk,                //System clock (10 MHz)
    input  wire       rst_n,              //Active-low reset 
    
    //SPI Physical Interface
    input  wire       sclk_in,            //SPI Clock 
    input  wire       ncs_in,             //Chip Select (Active Low)
    input  wire       copi_in,            //Controller Out Peripheral In 
    
    //Register Outputs to PWM Module 
    output reg [7:0]  en_reg_out_7_0,  
    output reg [7:0]  en_reg_out_15_8,
    output reg [7:0]  en_reg_pwm_7_0,    
    output reg [7:0]  en_reg_pwm_15_8,  
    output reg [7:0]  pwm_duty_cycle    
);

    //Clock Domain Crossing (CDC) Synchronizers
    // Using 3-stage flip-flop chains for sclk to enable stable edge detection 
    reg [2:0] sclk_sync;
    reg [1:0] ncs_sync;
    reg [1:0] copi_sync;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync <= 3'b0;
            ncs_sync  <= 2'b11; // NCS is active low, idle high
            copi_sync <= 2'b0;
        end else begin
            sclk_sync <= {sclk_sync[1:0], sclk_in};
            ncs_sync  <= {ncs_sync[0], ncs_in};
            copi_sync <= {copi_sync[0], copi_in};
        end
    end

    //Edge Detection
    wire sclk_rising_edge = (sclk_sync[2:1] == 2'b01); 
    wire ncs_rising_edge  = (ncs_sync[1:0]  == 2'b01);

    //Shift Register and Bit Counting
    reg [15:0] shift_reg;
    reg [4:0]  bit_count;
    reg        transaction_ready;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg <= 16'b0;
            bit_count <= 5'b0;
            transaction_ready <= 1'b0;
        end else begin
            //Transaction Finalization 
            //Detect the end of a valid 16-bit transaction FIRST before resetting bit_count
            if (ncs_rising_edge && (bit_count == 5'd16)) begin
                transaction_ready <= 1'b1;
            end else begin
                transaction_ready <= 1'b0;
            end

            //Bit Counting and Shifting Logic 
            if (ncs_sync[0]) begin
                //Reset counter ONLY if we aren't currently processing the rising edge of nCS
                if (!ncs_rising_edge) begin
                    bit_count <= 5'b0;
                end
            end else if (sclk_rising_edge) begin
                shift_reg <= {shift_reg[14:0], copi_sync[0]};
                bit_count <= bit_count + 1'b1;
            end
        end
    end

    //Register Mapping and Updates
    wire is_write = shift_reg[15];
    wire [6:0] addr = shift_reg[14:8];
    wire [7:0] data = shift_reg[7:0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            en_reg_out_7_0  <= 8'h00;
            en_reg_out_15_8 <= 8'h00;
            en_reg_pwm_7_0  <= 8'h00;
            en_reg_pwm_15_8 <= 8'h00;
            pwm_duty_cycle  <= 8'h00;
        end else if (transaction_ready && is_write) begin
            case (addr)
                7'h00: en_reg_out_7_0  <= data;
                7'h01: en_reg_out_15_8 <= data;
                7'h02: en_reg_pwm_7_0  <= data;
                7'h03: en_reg_pwm_15_8 <= data;
                7'h04: pwm_duty_cycle  <= data;
                default: ;
            endcase
        end
    end

endmodule


    