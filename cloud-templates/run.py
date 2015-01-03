#!/usr/bin/env python
import optparse, csv, sys, uuid, time, os,json
import boto.s3, boto.cloudformation as cf
from boto.s3.key import Key
import boto.ec2

REGION=None
KEYNAME=None
TAG=None
GATEWAY_EIPALLOC = None
STACK_GATEWAY_TEMPLATE="single-node-hadoop.template.json"
#STACK_GATEWAY_TEMPLATE="cloudera-hadoop.template.json"
STACK_VPC_TEMPLATE="main_VPC_stack.template.json"
TEMPLATES=[ STACK_GATEWAY_TEMPLATE, STACK_VPC_TEMPLATE ]


def _get_availability_zones():
    if _get_availability_zones.azs is None:
        _get_availability_zones.azs = boto.ec2.connect_to_region(REGION).get_all_zones()
    return _get_availability_zones.azs
_get_availability_zones.azs = None
def _get_bucket():
    return 'wordblip-templates-%s' %REGION
def upload_s3(paths=TEMPLATES):
    """ 
    Put all buckets in us-east-1, bug in boto.s3 throwing IllegalLocationConstraintException 
    """
    kw = dict()
    conn = boto.s3.connect_to_region("us-east-1", **kw)
    b = conn.lookup(_get_bucket()) 
    if b is None: 
        b = conn.create_bucket(_get_bucket())
    for p in paths:
        assert(os.path.isfile(p), "No file '%s'" %p)
    for fdir,fname in map(lambda p: os.path.split(p), paths):
        k = Key(b)
        k.key = fname
        k.set_contents_from_filename(os.path.join(fdir,fname))
def upload_template_s3(key, path):
    print "def upload_template_s3():"
    kw = dict()
    conn = boto.s3.connect_to_region("us-east-1", **kw)
    b = conn.get_bucket(_get_bucket())
    assert(os.path.isfile(path))
    fdir,fname = os.path.split(path)
    k = Key(b)
    k.key = key
    k.set_contents_from_filename(os.path.join(fdir,fname))

def create_gateway_stack(stack_name, capabilities=None, **kw):
    print "=="*20
    print "== create_stack: ", stack_name
    print "=="
    print "=="*20
    
    # UPLOAD TO S3:
    upload_template_s3(STACK_GATEWAY_TEMPLATE, STACK_GATEWAY_TEMPLATE)
    
    template_url = 'https://s3.amazonaws.com/wordblip-templates-%s/%s' %(REGION,STACK_GATEWAY_TEMPLATE)
    region = filter(lambda i: i.name == REGION, cf.regions())[0]
    conn = cf.CloudFormationConnection(region=region)
    #stack = conn.create_stack(stack_name, template_url=template_url, parameters=[], notification_arns=[], disable_rollback=False, timeout_in_minutes=None, capabilities=None, tags=None)
    parameters = []
    for item in kw.items():
        #parameters.append(dict(ParameterKey=item[0], ParameterValue=item[1]))
        parameters.append((item[0], item[1]))
        
    print "TEMPLATE: ", template_url
    print "PARAMETERS: ", parameters
    try:
        stack_id = conn.create_stack(stack_name, template_url=template_url, capabilities=capabilities, parameters=parameters)
    except boto.exception.BotoServerError, ex:
        print "BotoServerError: ", ex.error_message
        print "D: ", ex.__dict__
        d = json.loads(ex.error_message)
        if d['Error']['Code'] == 'AlreadyExistsException':
            print "ignore this exception"
            return None
        raise
    return stack_id


def create_stack(stack_name, template_file, capabilities=None, **kw):
    print "=="*20
    print "== create_stack: ", stack_name
    print "=="
    print "=="*20
    template_url = 'https://s3.amazonaws.com/wordblip-templates-%s/%s' %(REGION,template_file)
    region = filter(lambda i: i.name == REGION, cf.regions())[0]
    conn = cf.CloudFormationConnection(region=region)
    #stack = conn.create_stack(stack_name, template_url=template_url, parameters=[], notification_arns=[], disable_rollback=False, timeout_in_minutes=None, capabilities=None, tags=None)
    parameters = []
    for item in kw.items():
        #parameters.append(dict(ParameterKey=item[0], ParameterValue=item[1]))
        parameters.append((item[0], item[1]))
        
    print "TEMPLATE: ", template_url
    print "PARAMETERS: ", parameters
    try:
        stack_id = conn.create_stack(stack_name, template_url=template_url, capabilities=capabilities, parameters=parameters)
    except boto.exception.BotoServerError, ex:
        print "BotoServerError: ", ex.error_message
        print "D: ", ex.__dict__
        d = json.loads(ex.error_message)
        if d['Error']['Code'] == 'AlreadyExistsException':
            print "ignore this exception"
            return None
        raise
    return stack_id


def wait_for_complete(stack_id):
    region = filter(lambda i: i.name == REGION, cf.regions())[0]
    conn = cf.CloudFormationConnection(region=region)
    stack = None
    
    while 1:
        try:
            stack = conn.describe_stacks(stack_name_or_id=stack_id)[0]
        except boto.exception.BotoServerError, ex:
            print "BotoServerError: ", ex.error_message
            time.sleep(5)
        else:
            print stack.__dict__
            if stack.stack_status == 'CREATE_IN_PROGRESS':
                time.sleep(2)
                continue
            elif stack.stack_status == 'CREATE_COMPLETE':
                break
            raise RuntimeError, 'Failed to create stack: %s' %stack.stack_status
            
        
    return stack


def delete_all_stacks():
    stack_names = ['HadoopMainVPC',  'WordblipGateway']
    availability_zones = _get_availability_zones()
    for i in range(len(availability_zones)):
        stack_names.append('WordblipPrivateSubnet%d' %(i+1))
    print "=="*20
    print "=="*20     
    for stack_name in stack_names:
        print "== delete_stack: ", stack_name
        region = filter(lambda i: i.name == REGION, cf.regions())[0]
        conn = cf.CloudFormationConnection(region=region)
        try:
            stack_id = conn.delete_stack(stack_name)
        except boto.exception.BotoServerError, ex:
            print "BotoServerError: ", ex.error_message
            d = json.loads(ex.error_message)

    # wait for delete to complete
    print "=="*20
    for stack_name in stack_names:
        print "== wait for delete_stack: ", stack_name
        wait_for_delete(stack_name)
    print "=="*20


def wait_for_delete(stack_id):
    region = filter(lambda i: i.name == REGION, cf.regions())[0]
    conn = cf.CloudFormationConnection(region=region)
    stack = None
    
    while 1:
        try:
            stack = conn.describe_stacks(stack_name_or_id=stack_id)[0]
        except boto.exception.BotoServerError, ex:
            print "=    BotoServerError: ", ex.error_message
            break
        else:
            print "=    STATUS: ", stack.stack_status
            time.sleep(10)
            #if stack.stack_status == 'CREATE_IN_PROGRESS':
            #    time.sleep(2)
            #    continue
            #elif stack.stack_status == 'CREATE_COMPLETE':
            #    break
            #raise RuntimeError, 'Failed to create stack: %s' %stack.stack_status
        

def create_all_stacks():
    do_upload = True
    if do_upload:
        upload_s3()
        
    stack_name = 'HadoopMainVPC'
    stack_id = create_stack(stack_name, STACK_VPC_TEMPLATE, AvailabilityZone=_get_availability_zones()[0].name)
    
    if stack_id is not None:
        print "Stack ID: ", stack_id
        stack = wait_for_complete(stack_id)
    else:
        print "Stack Name: ", stack_name
        stack = wait_for_complete(stack_name)        

    output_d = dict(map(lambda i: (i.key,i.value), stack.outputs))
    print "OUTPUT: ", output_d
    vpc_id = output_d['VpcId']
    subnet_id = output_d['PublicSubnetA']
   
    # Create Private Subnets
    #private_subnet_id_list = _create_private_subnets(vpc_id, subnet_id, PrivateRouteTableId)
    
    gateway_private_ip = None
    stack_name = 'WordblipGateway'
    stack_id = create_gateway_stack(stack_name, capabilities=['CAPABILITY_IAM'], 
                              VpcId=vpc_id, SubnetId=subnet_id, KeyName=KEYNAME, TagGateway=TAG, AllocationId=GATEWAY_EIPALLOC)
      
    if stack_id is not None:
      print "Stack ID: ", stack_id
      stack = wait_for_complete(stack_id)
    else:
      print "Stack Name: ", stack_name
      stack = wait_for_complete(stack_name)     
          
    output_d = dict(map(lambda i: (i.key,i.value), stack.outputs))
    print "OUTPUT: ", output_d
    gateway_ipaddr = output_d['IPAddress']
    gateway_private_ip = output_d['PrivateIp']
    
    
def _create_private_subnets(vpc_id, subnet_id, PrivateRouteTableId):
    availability_zones = _get_availability_zones()
    private_subnet_list = []
    for i in range(len(availability_zones)):
        availability_zone = availability_zones[i]
        stack_name = 'WordblipPrivateSubnet%d' %(i+1)
        cidr_block = "10.0.%d.0/24" %(i+1)
        stack_id = create_stack(stack_name, 
                                STACK_PRIVATE_SUBNET_TEMPLATE, 
                                VpcId=vpc_id, 
                                KeyName=KEYNAME, 
                                PrivateRouteTableId=PrivateRouteTableId, 
                                AvailabilityZone=availability_zone.name,
                                CidrBlock=cidr_block)
        if stack_id is not None:
            print "Stack ID: ", stack_id
            stack = wait_for_complete(stack_id)
        else:
            print "Stack Name: ", stack_name
            stack = wait_for_complete(stack_name)
        
        private_subnet_list.append(dict(map(lambda i: (i.key,i.value), stack.outputs)))

    return map(lambda d: d['PrivateSubnetId'], private_subnet_list)

        
def set_region(region):
    global REGION,KEYNAME,TAG,GATEWAY_EIPALLOC
    REGION = region
    if REGION == 'us-west-2':
        KEYNAME = "wordblip"
        TAG = "Hadoop"
        GATEWAY_EIPALLOC = "eipalloc-5ebd703b"
    else:
        print >> sys.stderr, "unsupported region"
        usage()
        
def usage():
    print "USAGE: run.py [create,delete]"
    sys.exit(1)
    
    
def main():
    """
    """
    global REGION,KEYNAME,TAG,GATEWAY_EIPALLOC
    op = optparse.OptionParser(usage="USAGE: %prog [options] [create|delete]", 
             description=main.__doc__)
    op.add_option("-r", "--region",
                  action="store", dest="region", default=REGION,
                  help="region to deploy cloud-formation stacks")
    (options, args) = op.parse_args()
    if len(args) != 1: usage()
    command = args[0]
    set_region(options.region)
    if command == "create":
        create_all_stacks()
    elif command == "delete":
        delete_all_stacks()
    else:
        usage()


if __name__ == '__main__': main()
