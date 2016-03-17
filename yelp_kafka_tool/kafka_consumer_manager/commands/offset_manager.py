from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import sys

from kazoo.exceptions import NoNodeError

from yelp_kafka_tool.kafka_consumer_manager.util import prompt_user_input
from yelp_kafka_tool.util.zookeeper import ZK


class OffsetManagerBase(object):

    @classmethod
    def get_topics_from_consumer_group_id(
        cls,
        cluster_config,
        groupid,
        fail_on_error=True
    ):
        topics = []
        with ZK(cluster_config) as zk:
            # Query zookeeper to get the list of topics that this consumer is
            # subscribed to.
            try:
                topics = zk.get_my_subscribed_topics(groupid)
            except NoNodeError:
                if fail_on_error:
                    print(
                        "Error: Consumer Group ID {groupid} does not exist.".format(
                            groupid=groupid
                        ),
                        file=sys.stderr
                    )
                    sys.exit(1)

        return topics

    @classmethod
    def preprocess_args(
        cls,
        groupid,
        topic,
        partitions,
        cluster_config,
        client,
        fail_on_error=True
    ):
        if (partitions and (not topic)):
            print(
                "Error: Cannot specify partitions without topic name.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Get all the topics that this consumer is subscribed to.
        print(
            "Cluster name: {cluster_name}, consumer group: {groupid}".format(
                cluster_name=cluster_config.name,
                groupid=groupid,
            ),
        )
        topics = cls.get_topics_from_consumer_group_id(
            cluster_config,
            groupid,
            fail_on_error,
        )
        topics_dict = {}
        if topic:
            if topic not in topics:
                print(
                    "Error: Consumer {groupid} is not subscribed to topic:"
                    " {topic}.".format(
                        groupid=groupid,
                        topic=topic,
                    ),
                    file=sys.stderr,
                )
                if fail_on_error:
                    sys.exit(1)
                else:
                    return {}

            complete_partitions_list = client.get_partition_ids_for_topic(topic)
            if partitions:
                # If the user specified a topic and partition, just fetch those
                # offsets.
                if not set(partitions).issubset(complete_partitions_list):
                    print(
                        "Error: Some partitions amongst {partitions} are not "
                        "part of complete partition list {complete_list} for "
                        "topic: {topic}.".format(
                            partitions=', '.join(str(p) for p in partitions),
                            complete_list=', '.join(str(p) for p in complete_partitions_list),
                            topic=topic,
                        ),
                        file=sys.stderr,
                    )
                    if fail_on_error:
                        sys.exit(1)
                    else:
                        return {}
                topics_dict[topic] = partitions
            else:
                # If the user just gave us a topic, get offsets from all partitions.
                topics_dict[topic] = complete_partitions_list
        else:
            for topic in topics:
                # Get all the partitions for this topic
                partitions = client.get_partition_ids_for_topic(topic)
                topics_dict[topic] = partitions

        return topics_dict

    @classmethod
    def add_parser(cls, subparsers):
        cls.setup_subparser(subparsers)


class OffsetWriter(OffsetManagerBase):

    @classmethod
    def preprocess_args(
        cls,
        groupid,
        topic,
        partitions,
        cluster_config,
        client,
        fail_on_error=True
    ):
        topics_dict = super(OffsetWriter, cls).preprocess_args(
            groupid, topic, partitions, cluster_config, client, fail_on_error
        )
        topics_str = ""
        for local_topic, local_partitions in topics_dict.iteritems():
            temp_str = "Topic: {topic}, Partitions: {partitions}\n".format(
                topic=local_topic,
                partitions=local_partitions
            )
            topics_str = topics_str + temp_str

        if (not topic) or (not partitions):
            in_str = (
                "Offsets of all topics and partitions listed below "
                "shall be modified:\n{topics}\nIs this what you really "
                "intend? (y/n)".format(topics=topics_str)
            )
            prompt_user_input(in_str)

        return topics_dict