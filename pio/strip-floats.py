# PlatformIO/SCons injects Import and the requested construction environment.
Import('env')

# These options affect C++ only; putting them in build_flags also passes them to C.
env.AppendUnique(CXXFLAGS=["-fno-rtti", "-fno-threadsafe-statics", "-fno-use-cxa-atexit"])

#
# Dump build environment (for debug)
#print env.Dump()
#

flags = " ".join(env['LINKFLAGS'])
flags = flags.replace("-u _printf_float", "")
flags = flags.replace("-u _scanf_float", "")
newflags = flags.split()

env.Replace(
  LINKFLAGS=newflags
)
