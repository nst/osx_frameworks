#!/usr/bin/env python

# python osx_frameworks.py Tests
# python osx_frameworks.py > osx.dot
# dot -Tpdf osx.dot -o osx.pdf && open osx.pdf

import os
import popen2
import sys
import unittest
import pickle

def is_dylib(s):
    return s.endswith(".dylib")

def is_framework(s):
    return s.endswith(".framework")

def is_public_framework(s):
    return is_framework(s) and s.startswith("/System/Library/Frameworks")

def is_private(s):
    return s.startswith("/System/Library/PrivateFrameworks")

def all_frameworks():
    l = []
    for path in ["/System/Library/Frameworks", "/System/Library/PrivateFrameworks"]:
        l += [ os.path.join(path, x) for x in os.listdir(path) if x.endswith('.framework')]
    return l

def short_name_for_bundle(path):
    basename = os.path.basename(path)
    basename_no_ext = os.path.splitext(basename)[0]
    return basename_no_ext    

def bundle_path_for_bin (bin_path):
	if bin_path.endswith('.dylib') or bin_path.endswith('.framework'):
	   return bin_path
	
	for ext in [".framework", ".dylib"]:
		i = bin_path.rfind(ext)
		if i != -1:
			return bin_path[:i] + ext
	return bin_path

def dependancies_for_framework(path):
    
    if not path.endswith('.dylib'):
        bin = os.path.join(path, short_name_for_bundle(path))
        if not os.path.exists(bin):
            bin = os.path.sep.join([path, "Versions", "A", short_name_for_bundle(path)])
        if not os.path.exists(bin):
            bin = os.path.sep.join([path, "Versions", "B", short_name_for_bundle(path)])
        if not os.path.exists(bin):
            return set([])
    else:
        bin = path
    
    command = "/usr/bin/otool -L %s" % bin
    (stdout, stdin, stderr) = popen2.popen3(command)
    lines = stdout.readlines()
    deps = set([ bundle_path_for_bin(x.split(' ')[0][1:]) for x in lines if x.startswith('\t') ])
    if path in deps:
        deps.remove(path)
    return deps
    
def digraph(d):
    
    l = []
    l.append("digraph G {")
    l.append("\tnode [shape=box];")
    l.append("\tsplines=ortho;")
    l.append("\tranksep=4;")
    #l.append("\tcompound=true;")
    #l.append("\tfontname=Monaco;")
    #l.append("\tfontsize=10;")
    #l.append("\tratio=fill;")
    #l.append('\tsize="11.7,6";')
    #l.append('\tmargin=0.2;')
	
    l.append("""
	{Legend [shape=none, margin=0, label=<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">
         <TR>
          <TD COLSPAN="2"><B>OS X 10.10.2</B></TD>
         </TR>
         <TR>
          <TD COLSPAN="2">Frameworks dependancies</TD>
         </TR>
         <TR>
          <TD COLSPAN="2">2015-02-25 @nst021</TD>
         </TR>
         <TR>
          <TD>.framework</TD>
          <TD BGCOLOR="gold"></TD>
         </TR>
         <TR>
          <TD>.dylib</TD>
          <TD BGCOLOR="lightblue"></TD>
         </TR>
        </TABLE>
        >];
    }\n""")
    
    all_nodes = set()
    all_nodes.update(d.keys())
    all_nodes.update(reduce(lambda s1,s2:s1.copy().update(s2) if s1 else set([]), d.values()))

    cluster_for_node = {}

    int_nodes = set([])
    for i in all_nodes:
        parents = filter(lambda n : n != i and i.startswith(n), all_nodes)
        if len(parents) > 0:
            int_nodes.add(i)
    
    ext_nodes = all_nodes.difference(int_nodes)
    
    for i in ext_nodes:
        if is_private(i):
            continue
        
        color = "lightblue" if is_dylib(i) else "gold"
        
        l.append('\tsubgraph "cluster_%s" {' % i)
        l.append("\t\tstyle = filled;")
        l.append("\t\tcolor = %s;" % color)
        
        int_nodes = filter(lambda n : n != i and n.startswith(i), all_nodes)
        
        i_ = short_name_for_bundle(i)
        l.append('\t\t"%s" [label = "%s", style=filled, fillcolor="white"];' % (i, i_))
        for i_n in int_nodes:
            i_n_ = short_name_for_bundle(i_n)
            l.append('\t\t"%s" [label = "%s", style=filled, fillcolor="gold"];' % (i_n, i_n_))

        l.append("\t}")
    l.append("")
    
    #

    for n in all_nodes:
        if is_private(n):
            continue
        deps = d[n] if n in d else []
        for dep in deps:
            if is_private(dep):
                continue
                
            if dep.startswith(n):
                continue

            tails = []
            
            if n in ext_nodes:
                tails.append('ltail="cluster_%s"' % n)
            
            if dep in ext_nodes:
                tails.append('lhead="cluster_%s"' % dep)
            
            tails_string = ','.join(tails)
            tails_string_brackets = '[%s]' % tails_string if len(tails) > 0 else ""
            
            l.append('\t\"%s\" -> \"%s\" %s;' % (n, dep, tails_string_brackets))
    
    l.append("}")
        
    return '\n'.join(l)

def build_graph(frameworks_set):
    d = {}
    for f in frameworks_set:
        deps = dependancies_for_framework(f)
        d[f] = set(deps)
            
    return d

def discover_new_dependancies(d):

    d2 = d.copy()
    
    for deps in d.values():
        for f in deps:
            if f not in d2:
                d2[f] = dependancies_for_framework(f)
            
    return d2

def remove_direct_deps(d):
    
    d2 = d.copy()
    
    for k, deps in d.iteritems():
        dep_1_set = set(deps)
        for dep_1 in dep_1_set:
            if k == dep_1:
                if k in d2 and dep_1 in d2[k]:
                    d2[k].remove(dep_1)
                continue
            if dep_1 not in d2:
                continue
            dep_2_set = d2[dep_1]
            
            u = dep_1_set.intersection(dep_2_set)
            if dep_1 in u:
                u.remove(dep_1)
            
            for f in u:
                if f not in d2[k]:
                    continue
                d2[k].remove(f)
                    

    return d2

import unittest

class Tests(unittest.TestCase):

    def test_short_name_for_bundle(self):
        
        s = short_name_for_bundle('/System/Library/Frameworks/Accelerate.framework')
        self.assertEqual(s, 'Accelerate')

        s = short_name_for_bundle('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vImage.framework')
        self.assertEqual(s, 'vImage')

        s = short_name_for_bundle('/usr/lib/libSystem.B.dylib')
        self.assertEqual(s, 'libSystem.B')
    
    def test_dependancies_for_framework(self):

        deps = dependancies_for_framework('/System/Library/Frameworks/Accelerate.framework')
        
        self.assertTrue('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vecLib.framework' in deps)
        self.assertTrue('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vImage.framework' in deps)
        self.assertTrue('/usr/lib/libSystem.B.dylib' in deps)

    def test_dependancies_for_framework_2(self):
        
        deps = dependancies_for_framework('/System/Library/Frameworks/Foundation.framework')
        self.assertTrue('/System/Library/Frameworks/CoreFoundation.framework' in deps)

        deps = dependancies_for_framework('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vecLib.framework')
        self.assertTrue('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vecLib.framework/Versions/A/libvDSP.dylib' in deps)
        
        deps = dependancies_for_framework('/System/Library/Frameworks/vecLib.framework')
        self.assertTrue('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vecLib.framework/Versions/A/libLinearAlgebra.dylib' in deps)
        
        deps = dependancies_for_framework('/usr/lib/system/libquarantine.dylib')
        self.assertTrue('/usr/lib/system/libsystem_kernel.dylib' in deps)
        self.assertTrue('/usr/lib/system/libquarantine.dylib' not in deps)
    
    def test_bundle_path_for_bin(self):

        path = bundle_path_for_bin('/System/Library/Frameworks/Cocoa.framework/Versions/A/Cocoa')
        self.assertEqual(path, '/System/Library/Frameworks/Cocoa.framework')

        path = bundle_path_for_bin('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vImage.framework/Versions/A/vImage')
        self.assertEqual(path, '/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vImage.framework')
    
        path = bundle_path_for_bin('/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vecLib.framework/Versions/A/libvDSP.dylib')
        self.assertEqual(path, '/System/Library/Frameworks/Accelerate.framework/Versions/A/Frameworks/vecLib.framework/Versions/A/libvDSP.dylib')

    def test_remove_direct_dep(self):

        d = {}
        d['a'] = set(['b', 'c'])
        d['b'] = set(['c'])

        d2 = {}
        d2['a'] = set(['b'])
        d2['b'] = set(['c'])
        
        self.assertEqual(d2, remove_direct_deps(d))
            
if __name__ == '__main__':
    
    if len(sys.argv) > 1:
        unittest.main()
        sys.exit(0)
    
    sample_data = False    
    if not sample_data:
        filename = 'data.pickle'
        d_no_dd = None
        
        if os.path.exists(filename):
            d_no_dd = pickle.load(open(filename,"rb"))
        else:
            data = all_frameworks()
            d = build_graph(data)
            d2 = {}
            while d2 != d:
                d2 = discover_new_dependancies(d)
                d = d2
            
            d_no_dd = {}
            while d_no_dd != d:
                d_no_dd = remove_direct_deps(d)
                d = d_no_dd

            pickle.dump(d_no_dd, open(filename,"wb"))
        
        print digraph(d_no_dd)
    else:
        d = {}
        d['a'] = set(['ab', 'c'])
        d['b'] = set(['a', 'c'])
        d['c'] = set(['a', 'ca'])
        d['ca'] = set(['b'])            
        print digraph(d)
