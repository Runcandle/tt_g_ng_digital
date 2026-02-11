/*
 * Copyright (c) 2024 Gong Chen
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire       clk,                
    input  wire       rst_n,              
    
    // SPI Physical Interface
    input  wire       sclk_in,            
    input  wire       ncs_in,             
    input  wire       copi_in,            
    
    // Register Outputs
    output reg [7:0]  en_reg_out_7_0,     
    output reg [7:0]  en_reg_out_15_8,    
    output reg [7:0]  en_reg_pwm_7_0,     
    output reg [7:0]  en_reg_pwm_15_8,    
    output reg [7:0]  pwm_duty_cycle      
);

    //Reduced CDC Synchronizers
    reg [1:0] sclk_sync, ncs_sync, copi_sync;
    reg sclk_old;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync <= 2'b0;
            ncs_sync  <= 2'b11; 
            copi_sync <= 2'b0;
            sclk_old  <= 1'b0;
        end else begin
            sclk_sync <= {sclk_sync[0], sclk_in};
            ncs_sync  <= {ncs_sync[0], ncs_in};
            copi_sync <= {copi_sync[0], copi_in};
            sclk_old  <= sclk_sync[1];
        end
    end

    //Edge Detection
    wire sclk_rising_edge = (sclk_sync[1] && !sclk_old);
    wire ncs_rising_edge  = (ncs_sync[1]  && !ncs_sync[0]);

    //Optimized Shift Register and Bit Counting
    reg [15:0] shift_reg;
    reg [4:0]  bit_count; // 5 bits is the minimum required to count to 16

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg <= 16'b0;
            bit_count <= 5'b0;
        end else if (ncs_sync[1]) begin
            bit_count <= 5'b0;
        end else if (sclk_rising_edge) begin
            shift_reg <= {shift_reg[14:0], copi_sync[1]};
            bit_count <= bit_count + 1'b1;
        end
    end

    //Streamlined Register Updates
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            en_reg_out_7_0  <= 8'h00;
            en_reg_out_15_8 <= 8'h00;
            en_reg_pwm_7_0  <= 8'h00;
            en_reg_pwm_15_8 <= 8'h00;
            pwm_duty_cycle  <= 8'h00;
        end else if (ncs_rising_edge && (bit_count == 5'd16) && shift_reg[15]) begin
            // Register update logic triggered only on valid 16-bit write transactions
            case (shift_reg[14:8])
                7'h00: en_reg_out_7_0  <= shift_reg[7:0];
                7'h01: en_reg_out_15_8 <= shift_reg[7:0];
                7'h02: en_reg_pwm_7_0  <= shift_reg[7:0];
                7'h03: en_reg_pwm_15_8 <= shift_reg[7:0];
                7'h04: pwm_duty_cycle  <= shift_reg[7:0];
            endcase
        end
    end

endmodule


    