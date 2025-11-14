    #####################################################################
    # Configurable patch locations
    #
    # Change these two .set values per-kernel / per-build as needed.
    #####################################################################

    .set MACHCHK_VECTOR_ADDR,  0x00000204   # Machine check handler vector
    .set LR_DUMP_HANDLER_ADDR, 0x0000D500   # Free space for our handler


    #####################################################################
    # Hook machine check handler to our LR→UART dumper
    #####################################################################

    MAKEPATCH MACHCHK_VECTOR_ADDR
0:
    MAKEBRANCH LR_DUMP_HANDLER_ADDR   # branch to our handler
9:


    #####################################################################
    # LR → UART dumper
    #####################################################################

    MAKEPATCH LR_DUMP_HANDLER_ADDR
0:
    mflr    r10                # Save LR into r10

    # --- UART base address setup (unchanged) ---
    li      r7, 0x0200         # UART base low bits
    oris    r7, r7, 0x8000
    sldi    r7, r7, 32
    oris    r7, r7, 0xEA00     # r7 = 0x80000200EA000000

    # UART config: 115200,8,N,1 (unchanged)
    lis     r8, 0
    oris    r8, r8, 0xE601
    stw     r8, 0x101C(r7)

    # Send leading 'L'
    li      r8, 'L'
    slwi    r8, r8, 24
    stw     r8, 0x1014(r7)

tx_wait_L:
    sync
    isync
    lwz     r8, 0x1018(r7)
    rlwinm. r8, r8, 0, 6, 6    # TX ready?
    beq     tx_wait_L          # wait until ready

    # Print 16 hex nibbles of LR
    li      r9, 16             # nibble counter

nibble_loop:
    srdi    r8, r10, 60        # top nibble of r10
    rlwinm  r8, r8, 0, 28, 31  # mask to 4 bits
    cmpwi   r8, 10
    blt     digit_is_decimal

    # A–F
    addi    r8, r8, 'A' - 10
    b       digit_to_ascii_done

digit_is_decimal:
    # 0–9
    addi    r8, r8, '0'

digit_to_ascii_done:
    slwi    r8, r8, 24
    stw     r8, 0x1014(r7)

tx_wait_digit:
    sync
    isync
    lwz     r8, 0x1018(r7)
    rlwinm. r8, r8, 0, 6, 6    # TX ready?
    beq     tx_wait_digit      # wait until ready

    sldi    r10, r10, 4        # shift next nibble into MSB
    addi    r9, r9, -1
    cmpwi   r9, 0
    bne     nibble_loop        # loop until 16 nibbles sent

halt_forever:
	b halt_forever
9:
