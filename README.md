MCE to UART will replace the machine check handler in the xbox 360s hypervisor, and write the last stored link address to UART. I noticed that the machine check does a branch and link, so we take that link address and write it to UART. This is useful when debugging a machine check in the hypervisor, and will take you to or close to the offending code. 


PPC bin diff is useful for comparing a hardpatched SE image (like a shadowboot) and comparing to a clean SE, and will dump the changes to file. Very nice output, try it :)
