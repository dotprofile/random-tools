MCE to UART will replace the machine check handler in the xbox 360s hypervisor, and write the last stored link address to UART. I noticed that the machine check does a branch and link, so we take that link address and write it to UART. This is useful when debugging a machine check in the hypervisor, and will take you to or close to the offending code. 

In the header of the ASM file, there are 2 set variables you need to adjust per hypervisor. Find where the machine check handler is, (usually around address 0x200) and also find a big empty spot for the code to be stored. When a machine check occurs, it'll write the link address to UART and then halt. Also, this will prevent the post code from becoming 0xFF. 

Here is an example of the UART output 

<img width="380" height="179" alt="image" src="https://github.com/user-attachments/assets/b36583f0-9c33-4466-b9c7-6c7f0e885e7a" />


PPC bin diff is useful for comparing a hardpatched SE image (like a shadowboot) and comparing to a clean SE, and will dump the changes to file. Very nice output, try it :)


Example usage:

python .\ppc_bin_diff2.py '.\Output\clean 17489\hypervisor.bin' .\Output\rgl-proto\hypervisor.bin --endian big

<img width="632" height="822" alt="{E394BCC2-AA64-40FC-A828-E2225B1D0EC1}" src="https://github.com/user-attachments/assets/1e0af09e-4388-4c90-85e2-472c62595292" />


Will also emit patches in MAKEPATCH format, but beware, you need to fix up anything with a relative address emitted as an absolute address, as conditional branches etc need to be relative. It's good enough for getting started I suppose. It is not always aware if code was a .long instruction for data, for example, like setting a version.


python .\ppc_bin_diff2.py '.\Output\clean 17489\hypervisor.bin' .\Output\rgl-proto\hypervisor.bin --endian big --makepatch

<img width="616" height="861" alt="{43CBB51E-722A-4B79-BF44-F17389FF6B3B}" src="https://github.com/user-attachments/assets/081a8208-3b69-4ec5-9d79-ab2379608345" />
