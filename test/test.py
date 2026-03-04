# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    #Write your test here
    dut._log.info("Start SPI test")

    upper_freq = 3.0 * 1.01
    lower_freq = 3.0 * 0.99
    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    await send_spi_transaction(dut, 1, 0x00, 0x01)
    await send_spi_transaction(dut, 1, 0x02, 0x01)
    await send_spi_transaction(dut, 1, 0x04, 0x80)


    while((dut.uo_out.value.integer & 1) == 1):
        await ClockCycles(dut.clk, 1)
    
    # Read first rising edge
    while not (((dut.uo_out.value.integer) & 1) == 1):
        await ClockCycles(dut.clk, 1)
    t_rising_edge1 = cocotb.utils.get_sim_time(units="ns")
    
    # Falling edge after first rising edge
    while((dut.uo_out.value.integer & 1) == 1):
        await ClockCycles(dut.clk, 1)
    
    # Read second rising edge
    while not ((dut.uo_out.value.integer & 1) == 1):
        await ClockCycles(dut.clk, 1)
    t_rising_edge2 = cocotb.utils.get_sim_time(units="ns")
    
    period = t_rising_edge2 - t_rising_edge1
    frequency = (1000000.0 / period)
    
    assert (frequency <= upper_freq and frequency >= lower_freq), f"Frequency is {frequency}, Expected {lower_freq} <= {frequency} <= {upper_freq}"
    
    # Send spi transaction to PWM_DUTY_CYCLE with 0% duty cycle (signal is LOW)
    dut._log.info("Verifying frequency with 0 percent duty cycle")
    await send_spi_transaction(dut, 1, 0x04, 0x00)
    await ClockCycles(dut.clk, 5000)
    assert (dut.uo_out.value.integer & 1) == 0, "Signal is not low even with 0 percent duty cycle..."

    # Send spi transaction to PWM_DUTY_CYCLE with 100% duty cycle (signal is HIGH)
    dut._log.info("Verifying frequency with 100 percent duty cycle")
    await send_spi_transaction(dut, 1, 0x04, 0xFF)
    await ClockCycles(dut.clk, 5000)
    assert (dut.uo_out.value.integer & 1) == 1, "Signal is not HIGH even with 100 percent duty cycle..."

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("PWM Frequency test completed successfully")



@cocotb.test()
async def test_pwm_duty(dut):
        # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Initiate output streams
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    await send_spi_transaction(dut, 1, 0x02, 0x01)

    # perform sweep (16 <= t < 241) at increments of 32
    dut._log.info("Sweeping duty register values between 16 (inclusively) and 241 (exclusively)")
    for t in range(16, 241, 32):
        expected_duty = (t / 256.0) * 100
        upper_bound_duty = expected_duty * 1.01
        lower_bound_duty = expected_duty * 0.99

        dut._log.info(f"Sending {t} duty cycle to PWM output stream")
        await send_spi_transaction(dut, 1, 0x04, t)

        # Wait until current "hump" ends
        while(dut.uo_out.value.integer & 1) == 1:
            await ClockCycles(dut.clk, 1)
        
        # Wait for first rising edge
        while not (dut.uo_out.value.integer & 1) == 1:
            await ClockCycles(dut.clk, 1)
        t_rising_edge1 = cocotb.utils.get_sim_time(units="ns")

        # Wait for falling edge after first rising edge
        while (dut.uo_out.value.integer & 1) == 1:
            await ClockCycles(dut.clk, 1)
        t_falling_edge = cocotb.utils.get_sim_time(units="ns")

        while not (dut.uo_out.value.integer & 1) == 1:
            await ClockCycles(dut.clk, 1)
        t_rising_edge2 = cocotb.utils.get_sim_time(units="ns")

        high_time = t_falling_edge - t_rising_edge1
        period = t_rising_edge2 - t_rising_edge1
        duty_cycle = (high_time / period) * 100

        assert (lower_bound_duty <= duty_cycle <= upper_bound_duty), f"{duty_cycle} does not fall between {lower_bound_duty} and {upper_bound_duty}"
        dut._log.info(f"Duty cycle check for {t} complete")

    # Send spi transaction to PWM_DUTY_CYCLE with 0% duty cycle (signal is LOW)
    dut._log.info("Verifying 0 percent expected duty cycle")
    await send_spi_transaction(dut, 1, 0x04, 0x00)
    await ClockCycles(dut.clk, 5000)
    assert (dut.uo_out.value.integer & 1) == 0

    # Send spi transaction to PWM_DUTY_CYCLE with 100% duty cycle (signal is HIGH)
    dut._log.info("Verifying frequency with 100 percent duty cycle")
    await send_spi_transaction(dut, 1, 0x04, 0xFF)
    await ClockCycles(dut.clk, 5000)
    assert (dut.uo_out.value.integer & 1) == 1

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    
    dut._log.info("PWM Duty Cycle test completed successfully")